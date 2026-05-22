"""cedict_entries table for CC-CEDICT Chinese dictionary

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-22 00:00:00.000000
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE cedict_entries (
            id SERIAL PRIMARY KEY,
            traditional TEXT NOT NULL,
            simplified TEXT NOT NULL,
            pinyin TEXT NOT NULL,
            definitions JSONB NOT NULL DEFAULT '{}',
            hsk_level SMALLINT
        )
    """)
    # GIN trigram indexes for both script variants — enables LIKE / similarity queries
    op.execute(
        "CREATE INDEX idx_cedict_simplified_gin ON cedict_entries "
        "USING GIN (simplified gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX idx_cedict_traditional_gin ON cedict_entries "
        "USING GIN (traditional gin_trgm_ops)"
    )
    op.execute("CREATE INDEX idx_cedict_hsk ON cedict_entries (hsk_level)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_cedict_hsk")
    op.execute("DROP INDEX IF EXISTS idx_cedict_traditional_gin")
    op.execute("DROP INDEX IF EXISTS idx_cedict_simplified_gin")
    op.execute("DROP TABLE IF EXISTS cedict_entries")
