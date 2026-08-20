"""
Database Connection - Thread-local SQLite connection management

Provides thread-safe connection handling with a network-safe rollback journal.
"""

import sqlite3
import threading
import logging
from pathlib import Path
from typing import Optional, List
from contextlib import contextmanager


logger = logging.getLogger(__name__)


class DatabaseConnection:
    """
    Thread-local SQLite connection management with write locking.

    Provides:
    - Thread-safe connections via thread-local storage
    - Write lock for serializing database writes across threads
    - Network-safe rollback journal (DELETE) - NOT WAL, which corrupts over SMB
    - Foreign key support
    - Transaction context manager
    """

    def __init__(self, db_path: Path):
        """
        Initialize connection manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._local = threading.local()
        # Write lock to serialize database writes across threads in this process
        self._write_lock = threading.RLock()
        # Every connection handed out, so close_all() can close them ALL - not
        # just the calling thread's. Connections are thread-local, and worker
        # threads open their own (thumbnail loads, async apply). Without this,
        # switching library would leave those threads holding open handles on the
        # OLD database, which on Windows can pin the file.
        self._all_connections: List[sqlite3.Connection] = []
        self._connections_lock = threading.Lock()

    def get_connection(self) -> sqlite3.Connection:
        """
        Get thread-local database connection.

        Returns:
            SQLite connection for current thread
        """
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            # Journal mode: a rollback journal (DELETE), NOT WAL. This database
            # lives at {library}/.meta/database.db, which for studios sits on a
            # shared NETWORK drive - and SQLite's WAL mode relies on shared memory
            # (mmap) that is unreliable/unsupported over SMB shares and can CORRUPT
            # the database. DELETE is safe over network filesystems. The cost (a
            # reader briefly waits during a write's exclusive lock) is negligible
            # for this read-heavy, single-writer workload.
            # Switching an existing WAL database here checkpoints it and converts
            # to DELETE automatically (one-time, safe).
            try:
                conn.execute("PRAGMA journal_mode = DELETE")
            except sqlite3.Error as e:
                logger.warning(f"Could not set journal_mode=DELETE: {e}")
            # Wait for a busy lock instead of failing instantly (also covered by
            # the connect() timeout above; set explicitly for clarity).
            conn.execute("PRAGMA busy_timeout = 30000")
            # Row factory for dict-like access
            conn.row_factory = sqlite3.Row

            self._local.connection = conn
            with self._connections_lock:
                self._all_connections.append(conn)

        return self._local.connection

    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions with write locking.

        Usage:
            with connection.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(...)

        Automatically commits on success, rolls back on exception.
        Thread-safe: acquires write lock to serialize concurrent writes.
        """
        conn = self.get_connection()
        # Acquire write lock to serialize writes across threads
        with self._write_lock:
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e

    @contextmanager
    def read_only(self):
        """
        Context manager for read-only operations (no write lock needed).

        Usage:
            with connection.read_only() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ...")

        Does not acquire write lock, allowing concurrent reads.
        """
        conn = self.get_connection()
        yield conn

    def execute_write(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute a write operation with proper locking.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            Cursor with results
        """
        conn = self.get_connection()
        with self._write_lock:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor

    def close(self):
        """Close database connection for current thread."""
        conn = getattr(self._local, 'connection', None)
        if conn is None:
            return

        try:
            conn.close()
        except Exception as e:
            logger.warning(f"Error closing database connection: {e}")
        finally:
            self._local.connection = None
            with self._connections_lock:
                if conn in self._all_connections:
                    self._all_connections.remove(conn)

    def close_all(self):
        """
        Close EVERY connection this manager handed out, on any thread.

        Call on shutdown, and when switching library. This is deliberately not
        the same as close(): connections are thread-local, so close() only ever
        closes the caller's. Worker threads open their own, and those would keep
        the old database file open indefinitely.
        """
        with self._connections_lock:
            connections = list(self._all_connections)
            self._all_connections.clear()

        for conn in connections:
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"Error closing database connection: {e}")

        # Drop this thread's reference. Other threads' thread-local slots still
        # point at now-closed connections, which is fine: this manager is being
        # discarded, so nothing should call get_connection() on it again.
        self._local.connection = None


__all__ = ['DatabaseConnection']
