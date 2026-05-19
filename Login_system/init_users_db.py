import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from passlib.context import CryptContext

# Match Login_system/login_server.py hashing so seeded users authenticate normally.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from config import BCRYPT_ROUNDS
except Exception:
    BCRYPT_ROUNDS = 12

pwd_context = CryptContext(
    schemes=["bcrypt_sha256", "pbkdf2_sha256"],
    default="bcrypt_sha256",
    deprecated=["pbkdf2_sha256"],
    bcrypt_sha256__rounds=BCRYPT_ROUNDS,
)


def main():
    this_dir = os.path.dirname(__file__)
    db_path = os.path.join(this_dir, "users.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Create users table if missing (minimal subset used by auth)
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        role TEXT,
        mfa_enabled INTEGER DEFAULT 0,
        mfa_secret TEXT,
        active INTEGER DEFAULT 1,
        google_id TEXT UNIQUE,
        email TEXT,
        profile_picture TEXT,
        auth_provider TEXT DEFAULT 'local',
        email_verified INTEGER DEFAULT 0,
        full_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()

    # Dev users: password equals username (stored as a real hash, not empty string)
    now = datetime.utcnow().isoformat()
    users = [
        ("admin", pwd_context.hash("admin"), "admin", 1, now),
        ("employee", pwd_context.hash("employee"), "employee", 1, now),
    ]
    upsert_sql = """
        INSERT INTO users (username, password_hash, role, active, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            password_hash = excluded.password_hash,
            role = excluded.role,
            active = excluded.active,
            created_at = excluded.created_at
    """
    try:
        for username, pwd_hash, role, active, created_at in users:
            c.execute(upsert_sql, (username, pwd_hash, role, active, created_at))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"Created {db_path} with users: admin/admin, employee/employee (dev passwords)")


if __name__ == '__main__':
    main()
