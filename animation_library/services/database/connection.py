"""
Database Connection - Thread-local SQLite connection management

Provides thread-safe connection handling with WAL mode.
"""

import sqlite3
import threading
from pathlib import Path
from typing import Optional
from contextlib import contextmanager


class DatabaseConnection:
    """
    Thread-local SQLite connection management.

    Provides:
    - Thread-safe connections
    - WAL mode for better concurrency
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

    def get_connection(self) -> sqlite3.Connection:
        """
        Get thread-local database connection.

        Returns:
            SQLite connection for current thread
        """
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            # Enable foreign keys
            self._local.connection.execute("PRAGMA foreign_keys = ON")
            # Use WAL mode for better concurrency
            self._local.connection.execute("PRAGMA journal_mode = WAL")
            # Row factory for dict-like access
            self._local.connection.row_factory = sqlite3.Row

        return self._local.connection

    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions.

        Usage:
            with connection.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(...)

        Automatically commits on success, rolls back on exception.
        """
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e

    def close(self):
        """Close database connection for current thread."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


__all__ = ['DatabaseConnection']
