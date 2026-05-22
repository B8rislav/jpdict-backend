"""dictionary tables: jmdict_entries and kanjidic_entries

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-22 00:00:00.000000
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # JMdict: Japanese vocabulary (English + Russian glosses, JLPT levels)
    op.execute("""
        CREATE TABLE jmdict_entries (
            id SERIAL PRIMARY KEY,
            entry_id INTEGER NOT NULL UNIQUE,
            kanji_forms TEXT[] NOT NULL DEFAULT '{}',
            reading_forms TEXT[] NOT NULL DEFAULT '{}',
            senses JSONB NOT NULL DEFAULT '[]',
            jlpt_level SMALLINT,
            common BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)
    op.execute("CREATE INDEX idx_jmdict_kanji_gin ON jmdict_entries USING GIN (kanji_forms)")
    op.execute("CREATE INDEX idx_jmdict_reading_gin ON jmdict_entries USING GIN (reading_forms)")
    op.execute("CREATE INDEX idx_jmdict_jlpt ON jmdict_entries (jlpt_level)")

    # KANJIDIC2: individual kanji details with JLPT levels and component breakdown
    op.execute("""
        CREATE TABLE kanjidic_entries (
            character TEXT PRIMARY KEY CHECK (char_length(character) = 1),
            stroke_count SMALLINT,
            jlpt_level SMALLINT,
            grade SMALLINT,
            frequency SMALLINT,
            on_readings TEXT[] NOT NULL DEFAULT '{}',
            kun_readings TEXT[] NOT NULL DEFAULT '{}',
            meanings_en TEXT[] NOT NULL DEFAULT '{}',
            radical_number SMALLINT,
            components TEXT[] NOT NULL DEFAULT '{}'
        )
    """)
    op.execute("CREATE INDEX idx_kanjidic_jlpt ON kanjidic_entries (jlpt_level)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_kanjidic_jlpt")
    op.execute("DROP TABLE IF EXISTS kanjidic_entries")
    op.execute("DROP INDEX IF EXISTS idx_jmdict_jlpt")
    op.execute("DROP INDEX IF EXISTS idx_jmdict_reading_gin")
    op.execute("DROP INDEX IF EXISTS idx_jmdict_kanji_gin")
    op.execute("DROP TABLE IF EXISTS jmdict_entries")
