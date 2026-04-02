"""Database backup script."""

import shutil
from pathlib import Path
from datetime import datetime


def backup_database() -> None:
    """Backup the database."""
    db_path = Path("data/bot.db")
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"bot_{timestamp}.db"

    if db_path.exists():
        shutil.copy2(db_path, backup_path)
        print(f"Backup created: {backup_path}")
    else:
        print("Database not found")


if __name__ == "__main__":
    backup_database()
