"""SRS (SM-2) scheduling state on saved_words

Adds spaced-repetition columns so each SavedWord can act as a reviewable
Anki-style card: due_at, interval_days, ease_factor, repetitions, lapses,
last_reviewed_at, suspended. Adds a (user_id, language, due_at) index for the
"cards due now" query.

See TASKS.md Phase 17.1.

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-01 00:00:00.000000
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE saved_words
            ADD COLUMN due_at TIMESTAMPTZ,
            ADD COLUMN interval_days INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN ease_factor DOUBLE PRECISION NOT NULL DEFAULT 2.5,
            ADD COLUMN repetitions INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN lapses INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN last_reviewed_at TIMESTAMPTZ,
            ADD COLUMN suspended BOOLEAN NOT NULL DEFAULT false
    """)
    op.execute(
        "CREATE INDEX idx_saved_words_due ON saved_words (user_id, language, due_at)"
    )

    # Backfill existing saved words as immediately reviewable. SM-2 numeric
    # defaults (interval_days, ease_factor, repetitions, lapses, suspended) are
    # already applied by the column server defaults above; only due_at needs a
    # value so pre-existing words surface in the review queue right away.
    op.execute("UPDATE saved_words SET due_at = now() WHERE due_at IS NULL")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_saved_words_due")
    op.execute("""
        ALTER TABLE saved_words
            DROP COLUMN IF EXISTS suspended,
            DROP COLUMN IF EXISTS last_reviewed_at,
            DROP COLUMN IF EXISTS lapses,
            DROP COLUMN IF EXISTS repetitions,
            DROP COLUMN IF EXISTS ease_factor,
            DROP COLUMN IF EXISTS interval_days,
            DROP COLUMN IF EXISTS due_at
    """)
