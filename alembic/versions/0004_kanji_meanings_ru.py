"""Add meanings_ru column to kanjidic_entries

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-28 00:00:00.000000
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE kanjidic_entries "
        "ADD COLUMN meanings_ru TEXT[] NOT NULL DEFAULT '{}'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE kanjidic_entries DROP COLUMN IF EXISTS meanings_ru")
