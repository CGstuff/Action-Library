"""
Database Connection - Thread-local SQLite connection management

Provides thread-safe connection handling with WAL mode.
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
    - Write lock for serializing database writes (prevents WAL corruption)
    - WAL mode for better read concurrency
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
        # Write lock to serialize database writes across threads
        # This prevents potential WAL corruption with concurrent writes
        self._write_lock = threading.RLock()

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
            # Use WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode = WAL")
            # Row factory for dict-like access
            conn.row_factory = sqlite3.Row

            self._local.connection = conn

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
        if hasattr(self._local, 'connection') and self._local.connection:
            try:
                self._local.connection.close()
            except Exception as e:
                logger.warning(f"Error closing database connection: {e}")
            finally:
                self._local.connection = None

    def close_all(self):
        """
        Close the current thread's database connection.

        Call this during application shutdown. Note: Thread-local connections
        from other threads will be cleaned up when those threads exit.
        """
        self.close()


__all__ = ['DatabaseConnection']
