"""Reset database script."""

import os
from pathlib import Path


def reset_database() -> None:
    """Reset the database."""
    db_path = Path("data/bot.db")

    if db_path.exists():
        os.remove(db_path)
        print("Database reset")
    else:
        print("Database not found")


if __name__ == "__main__":
    reset_database()
