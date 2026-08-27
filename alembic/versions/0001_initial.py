"""Initial schema: users, speakers, tasks, uploads

Revision ID: 0001
Revises:
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('password_hash', sa.String(length=128), nullable=False),
        sa.Column('salt', sa.String(length=64), nullable=False),
        sa.Column('api_key', sa.String(length=128), nullable=False,
                  server_default=''),
        sa.Column('ocr_api_key', sa.String(length=128), nullable=False,
                  server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )
    op.create_table(
        'speakers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('photo_path', sa.Text(), nullable=False, server_default=''),
        sa.Column('bio', sa.Text(), nullable=False, server_default=''),
        sa.Column('bio_en', sa.Text(), nullable=False, server_default=''),
        sa.Column('institution', sa.String(length=256), nullable=False,
                  server_default=''),
        sa.Column('title', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'tasks',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('task_status', sa.String(length=16), nullable=False,
                  server_default='pending'),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('message', sa.String(length=512), nullable=False,
                  server_default=''),
        sa.Column('options', sa.Text(), nullable=True),
        sa.Column('pptx_path', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tasks_task_status', 'tasks', ['task_status'])
    op.create_table(
        'uploads',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('filename', sa.String(length=512), nullable=False,
                  server_default=''),
        sa.Column('path', sa.Text(), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('uploads')
    op.drop_index('ix_tasks_task_status', table_name='tasks')
    op.drop_table('tasks')
    op.drop_table('speakers')
    op.drop_table('users')
