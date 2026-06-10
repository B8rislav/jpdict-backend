"""first_reviewed_at on saved_words for the daily new-card cap

Records when a card was first ever reviewed so the review queue can enforce a
rolling, client-configurable daily limit on how many brand-new cards are
introduced. Nullable; never-reviewed cards stay NULL.

See TASKS.md Phase 17.7.

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-10 00:00:00.000000
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE saved_words ADD COLUMN first_reviewed_at TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE saved_words DROP COLUMN IF EXISTS first_reviewed_at")
