"""cedict flat definition columns and GIN trigram indexes for reverse search

Adds definitions_flat_en and definitions_flat_ru TEXT columns materialised from
the definitions JSONB, then creates gin_trgm_ops indexes on both for fast
prefix/trigram matching during English/Russian → Chinese reverse search.

Follows the same pattern as 0006 (jmdict flat gloss columns).

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-28 00:00:00.000000
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE cedict_entries
            ADD COLUMN definitions_flat_en TEXT,
            ADD COLUMN definitions_flat_ru TEXT
    """)

    # Backfill from existing rows
    op.execute("""
        UPDATE cedict_entries
        SET
            definitions_flat_en = (
                SELECT string_agg(g, E'\\n')
                FROM jsonb_array_elements_text(definitions -> 'en') g
            ),
            definitions_flat_ru = (
                SELECT string_agg(g, E'\\n')
                FROM jsonb_array_elements_text(definitions -> 'ru') g
            )
    """)

    op.execute(
        "CREATE INDEX idx_cedict_defs_en_gin ON cedict_entries "
        "USING GIN (definitions_flat_en gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX idx_cedict_defs_ru_gin ON cedict_entries "
        "USING GIN (definitions_flat_ru gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_cedict_defs_ru_gin")
    op.execute("DROP INDEX IF EXISTS idx_cedict_defs_en_gin")
    op.execute("""
        ALTER TABLE cedict_entries
            DROP COLUMN IF EXISTS definitions_flat_en,
            DROP COLUMN IF EXISTS definitions_flat_ru
    """)
