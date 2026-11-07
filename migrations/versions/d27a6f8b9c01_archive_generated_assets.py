"""Track durable generated media and its generation round."""

from alembic import op
import sqlalchemy as sa

revision = "d27a6f8b9c01"
down_revision = "c91d7e82a415"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ac_asset", sa.Column("generation_round", sa.Integer()))
    op.add_column("ac_asset", sa.Column("archive_key", sa.String(256)))
    op.add_column("ac_asset", sa.Column("archive_content_type", sa.String(64)))
    op.add_column("ac_asset", sa.Column("archive_size", sa.BigInteger()))
    op.add_column("ac_asset", sa.Column("archive_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ac_asset", sa.Column("archive_retry_at", sa.DateTime(timezone=True)))
    op.add_column("ac_asset", sa.Column("archive_error", sa.String(256)))


def downgrade() -> None:
    for column in ("archive_error", "archive_retry_at", "archive_attempts", "archive_size",
                   "archive_content_type", "archive_key", "generation_round"):
        op.drop_column("ac_asset", column)
