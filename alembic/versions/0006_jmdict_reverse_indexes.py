"""jmdict flat gloss columns and GIN trigram indexes for reverse search

Adds senses_glosses_en and senses_glosses_ru TEXT columns materialised from the
senses JSONB, then creates gin_trgm_ops indexes on both for fast prefix/trigram
matching during English/Russian → Japanese reverse search.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-28 00:00:00.000000
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute("""
        ALTER TABLE jmdict_entries
            ADD COLUMN senses_glosses_en TEXT,
            ADD COLUMN senses_glosses_ru TEXT
    """)

    # Backfill from existing rows
    op.execute("""
        UPDATE jmdict_entries
        SET
            senses_glosses_en = (
                SELECT string_agg(g, E'\\n')
                FROM jsonb_array_elements(senses) s,
                     jsonb_array_elements_text(s -> 'en') g
            ),
            senses_glosses_ru = (
                SELECT string_agg(g, E'\\n')
                FROM jsonb_array_elements(senses) s,
                     jsonb_array_elements_text(s -> 'ru') g
            )
    """)

    op.execute(
        "CREATE INDEX idx_jmdict_glosses_en_gin ON jmdict_entries "
        "USING GIN (senses_glosses_en gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX idx_jmdict_glosses_ru_gin ON jmdict_entries "
        "USING GIN (senses_glosses_ru gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_jmdict_glosses_ru_gin")
    op.execute("DROP INDEX IF EXISTS idx_jmdict_glosses_en_gin")
    op.execute("""
        ALTER TABLE jmdict_entries
            DROP COLUMN IF EXISTS senses_glosses_en,
            DROP COLUMN IF EXISTS senses_glosses_ru
    """)
