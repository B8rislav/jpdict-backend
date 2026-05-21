"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-19 00:00:00.000000
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')
    op.execute("CREATE TYPE language_enum AS ENUM ('jp', 'cn')")
    op.execute("CREATE TYPE word_status AS ENUM ('new', 'learning', 'known')")
    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR NOT NULL UNIQUE,
            hashed_password VARCHAR NOT NULL,
            language language_enum NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE saved_words (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            language language_enum NOT NULL,
            expression TEXT NOT NULL,
            reading TEXT NOT NULL,
            meaning TEXT NOT NULL,
            jlpt_level SMALLINT CONSTRAINT ck_jlpt_level CHECK (jlpt_level BETWEEN 1 AND 5),
            hsk_level SMALLINT CONSTRAINT ck_hsk_level CHECK (hsk_level BETWEEN 1 AND 6),
            status word_status NOT NULL DEFAULT 'new',
            added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_user_word UNIQUE (user_id, language, expression)
        )
    """)
    op.execute("""
        CREATE TABLE search_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            language language_enum NOT NULL,
            query TEXT NOT NULL,
            query_type VARCHAR(20) NOT NULL,
            searched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE kanji_cache (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            character VARCHAR(10) NOT NULL UNIQUE,
            data JSONB NOT NULL,
            cached_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX idx_saved_words_user_lang ON saved_words (user_id, language)")
    op.execute("CREATE INDEX idx_saved_words_expression_trgm ON saved_words USING GIN (expression gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_saved_words_expression_trgm")
    op.execute("DROP INDEX IF EXISTS idx_saved_words_user_lang")
    op.execute("DROP TABLE IF EXISTS kanji_cache")
    op.execute("DROP TABLE IF EXISTS search_history")
    op.execute("DROP TABLE IF EXISTS saved_words")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TYPE IF EXISTS word_status")
    op.execute("DROP TYPE IF EXISTS language_enum")
