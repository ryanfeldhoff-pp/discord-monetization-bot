"""Database configuration."""

import sqlite3
from pathlib import Path


class DatabaseConfig:
    """Database configuration."""

    def __init__(self, db_path: str = "data/bot.db"):
        """Initialize.

        Args:
            db_path: Path to database file.
        """
        self.db_path = db_path
        self.connection = None

    def connect(self) -> sqlite3.Connection:
        """Connect to database.

        Returns:
            Database connection.
        """
        Path(self.db_path).parent.mkdir(exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        return self.connection

    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
