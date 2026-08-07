import sqlite3
import hashlib
import os
import secrets
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app_data.db')


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,
            password_hash TEXT   NOT NULL,
            salt          TEXT   NOT NULL,
            api_key       TEXT   DEFAULT '',
            created_at    TEXT   DEFAULT (datetime('now','localtime'))
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS speakers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            photo_path  TEXT DEFAULT '',
            bio         TEXT DEFAULT '',
            institution TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
    try:
        conn.execute('ALTER TABLE speakers ADD COLUMN institution TEXT DEFAULT \'\'')
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute('ALTER TABLE users ADD COLUMN ocr_api_key TEXT DEFAULT \'\'')
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def _hash_password(password: str, salt: Optional[str] = None) -> tuple:
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
    return h, salt


def create_user(username: str, password: str, api_key: str = '',
                ocr_api_key: str = '') -> Optional[int]:
    conn = _connect()
    try:
        pwd_hash, salt = _hash_password(password)
        cur = conn.execute(
            'INSERT INTO users (username, password_hash, salt, api_key, ocr_api_key) '
            'VALUES (?, ?, ?, ?, ?)',
            (username.strip(), pwd_hash, salt, api_key.strip(), ocr_api_key.strip())
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def authenticate(username: str, password: str) -> Optional[dict]:
    conn = _connect()
    row = conn.execute(
        'SELECT id, username, password_hash, salt, api_key, ocr_api_key '
        'FROM users WHERE username = ?',
        (username.strip(),)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    pwd_hash, _ = _hash_password(password, row['salt'])
    if pwd_hash != row['password_hash']:
        return None
    return {'id': row['id'], 'username': row['username'],
            'api_key': row['api_key'], 'ocr_api_key': row['ocr_api_key']}


def get_user(user_id: int) -> Optional[dict]:
    conn = _connect()
    row = conn.execute(
        'SELECT id, username, api_key, ocr_api_key FROM users WHERE id = ?', (user_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {'id': row['id'], 'username': row['username'],
            'api_key': row['api_key'], 'ocr_api_key': row['ocr_api_key']}


def update_api_key(user_id: int, api_key: str):
    conn = _connect()
    conn.execute('UPDATE users SET api_key = ? WHERE id = ?', (api_key.strip(), user_id))
    conn.commit()
    conn.close()


def update_ocr_api_key(user_id: int, ocr_api_key: str):
    conn = _connect()
    conn.execute('UPDATE users SET ocr_api_key = ? WHERE id = ?',
                 (ocr_api_key.strip(), user_id))
    conn.commit()
    conn.close()


def update_user(user_id: int, username: str, api_key: str, ocr_api_key: str) -> bool:
    """Update user profile fields. Returns False if username is taken by another user."""
    conn = _connect()
    try:
        conn.execute(
            'UPDATE users SET username = ?, api_key = ?, ocr_api_key = ? WHERE id = ?',
            (username.strip(), api_key.strip(), ocr_api_key.strip(), user_id)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def update_password(user_id: int, new_password: str):
    """Update password with new salt + hash."""
    pwd_hash, salt = _hash_password(new_password)
    conn = _connect()
    conn.execute(
        'UPDATE users SET password_hash = ?, salt = ? WHERE id = ?',
        (pwd_hash, salt, user_id)
    )
    conn.commit()
    conn.close()


def save_speaker(name: str, photo_path: str = '', bio: str = '', institution: str = ''):
    conn = _connect()
    conn.execute(
        'INSERT OR REPLACE INTO speakers (name, photo_path, bio, institution) '
        'VALUES (?, ?, ?, ?)',
        (name.strip(), photo_path, bio, institution)
    )
    conn.commit()
    conn.close()


def load_speakers() -> list:
    conn = _connect()
    rows = conn.execute(
        'SELECT name, photo_path, bio, institution FROM speakers ORDER BY name'
    ).fetchall()
    conn.close()
    return [{'name': r['name'], 'photo_path': r['photo_path'], 'bio': r['bio'],
             'institution': r['institution']}
            for r in rows]


def delete_speaker(name: str):
    conn = _connect()
    conn.execute('DELETE FROM speakers WHERE name = ?', (name.strip(),))
    conn.commit()
    conn.close()
