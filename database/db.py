"""Data access layer — SQLAlchemy ORM over SQLite (dev/test) or PostgreSQL.

Public functions keep the exact signatures the desktop UI used with the old
raw-sqlite implementation, so the desktop app is unaffected by the migration.

DATABASE_URL comes from .env (see .env.example); falls back to a SQLite file
anchored at the project root.
"""
import hashlib
import os
import secrets
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from database.models import Base, Speaker, SystemSetting, Task, Upload, User

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

_DEFAULT_DB_URL = f'sqlite:///{(BASE_DIR / "app_data.db").as_posix()}'
DATABASE_URL = os.environ.get('DATABASE_URL', _DEFAULT_DB_URL)

# Relative SQLite paths anchor at the project root, not the process CWD
if DATABASE_URL.startswith('sqlite'):
    _prefix, _, _path = DATABASE_URL.partition('///')
    if _path and _path != ':memory:' and not Path(_path).is_absolute():
        DATABASE_URL = f'sqlite:///{(BASE_DIR / _path).as_posix()}'

# SQLite needs these pragmas; harmless extras ignored on other engines.
_engine_kwargs = {}
if DATABASE_URL.startswith('sqlite'):
    _engine_kwargs['connect_args'] = {'check_same_thread': False}

engine = create_engine(DATABASE_URL, pool_pre_ping=True, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    """Create missing tables (SQLite dev path) and backfill columns added
    after the original raw-sqlite schema. Alembic manages Postgres/CI
    migrations; this keeps the desktop app working against old SQLite DBs."""
    Base.metadata.create_all(engine)
    if DATABASE_URL.startswith('sqlite'):
        _backfill_legacy_columns()


def _backfill_legacy_columns():
    """ALTER TABLE ADD COLUMN for columns new models expect but old SQLite
    databases (created by the raw-sqlite schema) don't have."""
    import sqlite3

    db_path = engine.url.database or ''
    if not db_path or not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    try:
        for table, cols in (
            ('users', {'ocr_api_key': "TEXT DEFAULT ''",
                       'updated_at': 'TIMESTAMP',
                       'is_admin': 'INTEGER DEFAULT 0'}),
            ('speakers', {'institution': "TEXT DEFAULT ''",
                          'bio_en': "TEXT DEFAULT ''",
                          'title': "TEXT DEFAULT ''",
                          'updated_at': 'TIMESTAMP'}),
        ):
            existing = {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}
            for col, ddl in cols.items():
                if col not in existing:
                    conn.execute(f'ALTER TABLE {table} ADD COLUMN {col} {ddl}')
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Users — signatures unchanged from the raw-sqlite implementation
# ---------------------------------------------------------------------------

def _hash_password(password: str, salt: Optional[str] = None) -> tuple:
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
    return h, salt


def _user_to_dict(u: User) -> dict:
    return {'id': u.id, 'username': u.username,
            'api_key': u.api_key or '', 'ocr_api_key': u.ocr_api_key or '',
            'is_admin': bool(u.is_admin)}


def create_user(username: str, password: str, api_key: str = '',
                ocr_api_key: str = '') -> Optional[int]:
    with SessionLocal() as s:
        pwd_hash, salt = _hash_password(password)
        u = User(username=username.strip(), password_hash=pwd_hash, salt=salt,
                 api_key=api_key.strip(), ocr_api_key=ocr_api_key.strip())
        s.add(u)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            return None
        return u.id


def authenticate(username: str, password: str) -> Optional[dict]:
    with SessionLocal() as s:
        u = s.scalar(select(User).where(User.username == username.strip()))
        if u is None:
            return None
        pwd_hash, _ = _hash_password(password, u.salt)
        if pwd_hash != u.password_hash:
            return None
        return _user_to_dict(u)


def get_user(user_id: int) -> Optional[dict]:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        return _user_to_dict(u) if u else None


def update_api_key(user_id: int, api_key: str):
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if u:
            u.api_key = api_key.strip()
            s.commit()


def update_ocr_api_key(user_id: int, ocr_api_key: str):
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if u:
            u.ocr_api_key = ocr_api_key.strip()
            s.commit()


def update_user(user_id: int, username: str, api_key: str, ocr_api_key: str) -> bool:
    """Update user profile fields. Returns False if username is taken by another user."""
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if u is None:
            return False
        u.username = username.strip()
        u.api_key = api_key.strip()
        u.ocr_api_key = ocr_api_key.strip()
        try:
            s.commit()
            return True
        except IntegrityError:
            s.rollback()
            return False


def update_password(user_id: int, new_password: str):
    """Update password with new salt + hash."""
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if u:
            pwd_hash, salt = _hash_password(new_password)
            u.password_hash = pwd_hash
            u.salt = salt
            s.commit()


def list_users() -> list:
    """List all users. Never returns password hashes or API keys."""
    with SessionLocal() as s:
        rows = s.scalars(select(User).order_by(User.id)).all()
        return [{'id': u.id, 'username': u.username,
                 'is_admin': bool(u.is_admin),
                 'created_at': u.created_at.isoformat() if u.created_at else None,
                 'api_key_configured': bool((u.api_key or '').strip()),
                 'ocr_key_configured': bool((u.ocr_api_key or '').strip())}
                for u in rows]


def delete_user(user_id: int) -> bool:
    """Delete a user. Their tasks/uploads keep user_id NULL via FK SET NULL."""
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if u is None:
            return False
        s.delete(u)
        s.commit()
        return True


def set_admin(user_id: int, is_admin: bool) -> bool:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if u is None:
            return False
        u.is_admin = is_admin
        s.commit()
        return True


def ensure_admin() -> Optional[str]:
    """If users exist but none is admin (e.g. desktop-app legacy data),
    promote the earliest-registered user. Returns the promoted username."""
    with SessionLocal() as s:
        if s.scalar(select(User).where(User.is_admin.is_(True))) is not None:
            return None
        first = s.scalar(select(User).order_by(User.id).limit(1))
        if first is None:
            return None
        first.is_admin = True
        s.commit()
        return first.username


# ---------------------------------------------------------------------------
# Speakers — signatures unchanged from the raw-sqlite implementation
# ---------------------------------------------------------------------------

def save_speaker(name: str, photo_path: str = '', bio: str = '', institution: str = ''):
    """Insert or replace a speaker by name (matches old INSERT OR REPLACE)."""
    with SessionLocal() as s:
        sp = s.scalar(select(Speaker).where(Speaker.name == name.strip()))
        if sp is None:
            sp = Speaker(name=name.strip())
            s.add(sp)
        sp.photo_path = photo_path
        sp.bio = bio
        sp.institution = institution
        s.commit()


def load_speakers() -> list:
    with SessionLocal() as s:
        rows = s.scalars(select(Speaker).order_by(Speaker.name)).all()
        return [{'name': r.name, 'photo_path': r.photo_path, 'bio': r.bio,
                 'institution': r.institution}
                for r in rows]


def delete_speaker(name: str):
    with SessionLocal() as s:
        sp = s.scalar(select(Speaker).where(Speaker.name == name.strip()))
        if sp:
            s.delete(sp)
            s.commit()


# ---------------------------------------------------------------------------
# Tasks — web generation task persistence
# ---------------------------------------------------------------------------

def create_task(task_id: str, options: Optional[dict] = None,
                user_id: Optional[int] = None) -> str:
    import json
    with SessionLocal() as s:
        t = Task(id=task_id, user_id=user_id, task_status='pending',
                 progress=0, message='等待生成',
                 options=json.dumps(options, ensure_ascii=False) if options else None)
        s.add(t)
        s.commit()
        return t.id


def get_task(task_id: str) -> Optional[dict]:
    with SessionLocal() as s:
        t = s.get(Task, task_id)
        return _task_to_dict(t) if t else None


def update_task(task_id: str, **fields) -> bool:
    """Update task fields by keyword. Returns False if the task doesn't exist."""
    import json
    with SessionLocal() as s:
        t = s.get(Task, task_id)
        if t is None:
            return False
        if 'options' in fields and isinstance(fields['options'], (dict, list)):
            fields['options'] = json.dumps(fields['options'], ensure_ascii=False)
        for k, v in fields.items():
            if hasattr(t, k):
                setattr(t, k, v)
        s.commit()
        return True


def list_tasks(limit: int = 100) -> list:
    with SessionLocal() as s:
        rows = s.scalars(
            select(Task).order_by(Task.created_at.desc()).limit(limit)).all()
        return [_task_to_dict(t) for t in rows]


def _task_to_dict(t: Task) -> dict:
    import json
    options = None
    if t.options:
        try:
            options = json.loads(t.options)
        except ValueError:
            options = t.options
    return {
        'task_id': t.id,
        'user_id': t.user_id,
        'task_status': t.task_status,
        'progress': t.progress,
        'message': t.message,
        'options': options,
        'pptx_path': t.pptx_path,
        'error': t.error,
        'created_at': t.created_at.isoformat() if t.created_at else None,
        'updated_at': t.updated_at.isoformat() if t.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Uploads — web upload persistence
# ---------------------------------------------------------------------------

def create_upload(file_id: str, filename: str, path: str, size: int,
                  user_id: Optional[int] = None) -> str:
    with SessionLocal() as s:
        u = Upload(id=file_id, user_id=user_id, filename=filename,
                   path=path, size=size)
        s.add(u)
        s.commit()
        return u.id


def get_upload(file_id: str) -> Optional[dict]:
    with SessionLocal() as s:
        u = s.get(Upload, file_id)
        return {'file_id': u.id, 'filename': u.filename, 'path': u.path,
                'size': u.size, 'user_id': u.user_id} if u else None


def list_uploads() -> list:
    with SessionLocal() as s:
        rows = s.scalars(select(Upload).order_by(Upload.created_at)).all()
        return [{'file_id': u.id, 'filename': u.filename, 'path': u.path,
                 'size': u.size} for u in rows]


# ---------------------------------------------------------------------------
# Shared API keys — 全体用户共享使用、仅管理员可见可改，密文落库
# ---------------------------------------------------------------------------

_SHARED_KEY_DEEPSEEK = 'shared_deepseek_api_key'
_SHARED_KEY_OCR = 'shared_ocr_api_key'


def get_shared_keys() -> dict:
    """读取共享 API Key（解密）。返回 {'api_key': str, 'ocr_api_key': str}。"""
    from utils.crypto import decrypt_secret
    with SessionLocal() as s:
        rows = {r.key: r.value for r in s.scalars(select(SystemSetting))}
    return {
        'api_key': decrypt_secret(rows.get(_SHARED_KEY_DEEPSEEK, '')),
        'ocr_api_key': decrypt_secret(rows.get(_SHARED_KEY_OCR, '')),
    }


def set_shared_keys(api_key: Optional[str] = None,
                    ocr_api_key: Optional[str] = None) -> dict:
    """更新共享 API Key（加密后落库）。None=保持不变，空串=清空。返回更新后的值。"""
    from utils.crypto import encrypt_secret
    with SessionLocal() as s:
        for key, val in ((_SHARED_KEY_DEEPSEEK, api_key),
                         (_SHARED_KEY_OCR, ocr_api_key)):
            if val is None:
                continue
            row = s.get(SystemSetting, key)
            cipher = encrypt_secret((val or '').strip())
            if row is None:
                s.add(SystemSetting(key=key, value=cipher))
            else:
                row.value = cipher
        s.commit()
    return get_shared_keys()
