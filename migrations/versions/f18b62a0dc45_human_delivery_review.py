"""Bind a human decision and a copy review request to a machine report."""

from alembic import op
import sqlalchemy as sa

revision = "f18b62a0dc45"
down_revision = "d27a6f8b9c01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ac_compliance_report", sa.Column("request_key", sa.String(128)))
    op.add_column("ac_compliance_report", sa.Column("human_decision", sa.String(16)))
    op.add_column("ac_compliance_report", sa.Column("human_reviewer_id", sa.String(32)))
    op.add_column("ac_compliance_report", sa.Column("human_reviewed_at", sa.DateTime(timezone=True)))
    op.add_column("ac_compliance_report", sa.Column("human_note", sa.String(1000)))


def downgrade() -> None:
    for column in ("human_note", "human_reviewed_at", "human_reviewer_id", "human_decision", "request_key"):
        op.drop_column("ac_compliance_report", column)
