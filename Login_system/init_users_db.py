import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from Login_system.login_server import init_db, DB_PATH  # noqa: E402
from Login_system.dev_users import dev_user_summary  # noqa: E402


def main():
    db_path = Path(DB_PATH)
    if db_path.exists():
        db_path.unlink()
        print(f"Deleted existing {db_path}")

    init_db()
    print(f"Created fresh {db_path} with users: {dev_user_summary()}")


if __name__ == "__main__":
    main()
