"""reibun_entries table for Tatoeba example sentences

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-28 00:00:00.000000
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE reibun_entries (
            id BIGSERIAL PRIMARY KEY,
            sentence_jp TEXT NOT NULL,
            reading_jp TEXT NULL,
            translation_ru TEXT NULL,
            translation_en TEXT NULL,
            source TEXT NOT NULL,
            source_sentence_id BIGINT NULL
        )
    """)
    op.execute(
        "CREATE INDEX idx_reibun_sentence_jp_gin ON reibun_entries "
        "USING GIN (sentence_jp gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX idx_reibun_source_sentence_id ON reibun_entries (source_sentence_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_reibun_source_sentence_id")
    op.execute("DROP INDEX IF EXISTS idx_reibun_sentence_jp_gin")
    op.execute("DROP TABLE IF EXISTS reibun_entries")
