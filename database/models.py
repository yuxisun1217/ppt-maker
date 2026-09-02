"""SQLAlchemy ORM models. Works on both SQLite (dev/test) and PostgreSQL.

Schema notes:
- users/speakers carry over the desktop app's schema (raw-sqlite era) plus
  new updated_at columns; existing SQLite DBs are upgraded in-place by
  init_db()'s legacy-column backfill.
- tasks/uploads back the web backend; user_id is nullable until web auth
  lands (TODO).
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    salt: Mapped[str] = mapped_column(String(64), nullable=False)
    api_key: Mapped[str] = mapped_column(String(128), default='')
    ocr_api_key: Mapped[str] = mapped_column(String(128), default='')
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now())

    tasks: Mapped[list['Task']] = relationship(back_populates='user')
    uploads: Mapped[list['Upload']] = relationship(back_populates='user')


class Speaker(Base):
    __tablename__ = 'speakers'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    photo_path: Mapped[str] = mapped_column(Text, default='')
    bio: Mapped[str] = mapped_column(Text, default='')
    bio_en: Mapped[str] = mapped_column(Text, default='')
    institution: Mapped[str] = mapped_column(String(256), default='')
    title: Mapped[str] = mapped_column(String(64), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now())


class Task(Base):
    """Web generation task. task_id is a 32-char hex UUID string."""

    __tablename__ = 'tasks'

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    task_status: Mapped[str] = mapped_column(String(16), default='pending', index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(String(512), default='')
    options: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON, no secrets
    pptx_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # traceback
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped[Optional['User']] = relationship(back_populates='tasks')


class Upload(Base):
    """Web upload record; file_id is a 32-char hex UUID string."""

    __tablename__ = 'uploads'

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    filename: Mapped[str] = mapped_column(String(512), default='')
    path: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped[Optional['User']] = relationship(back_populates='uploads')


class SystemSetting(Base):
    """全局系统设置（key-value）。共享 API Key 经 utils.crypto 加密后存 value。"""

    __tablename__ = 'system_settings'

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default='')
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now())
