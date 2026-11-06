"""Durable remote video jobs and workflow recovery boundaries.

Revision ID: c91d7e82a415
Revises: b82f91d4e630
"""

import sqlalchemy as sa
from alembic import op

revision = "c91d7e82a415"
down_revision = "b82f91d4e630"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "ac_asset", "url", existing_type=sa.String(512), type_=sa.String(8192)
    )
    for column in (
        sa.Column("state_snapshot", sa.JSON()),
        sa.Column("provider_snapshot_enc", sa.JSON()),
        sa.Column("next_node", sa.String(64)),
        sa.Column("in_flight_node", sa.String(64)),
        sa.Column("next_poll_at", sa.DateTime(timezone=True)),
    ):
        op.add_column("ac_task_execution", column)
    op.create_index(
        "ix_ac_task_execution_next_poll_at", "ac_task_execution", ["next_poll_at"]
    )
    for table, name in (
        ("ac_asset", "uq_asset_provider_job"),
        ("ac_task_node_run", "uq_node_provider_job"),
    ):
        op.add_column(table, sa.Column("provider_job_id", sa.String(32)))
        op.create_index(name, table, ["tenant_id", "provider_job_id"], unique=True)
    op.create_table(
        "ac_provider_job",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("tenant_id", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(32)),
        sa.Column("updated_by", sa.String(32)),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.SmallInteger(), nullable=False),
        sa.Column("task_id", sa.String(32), nullable=False),
        sa.Column("execution_id", sa.String(32), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.String(32)),
        sa.Column("adapter", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("api_base", sa.String(512), nullable=False),
        sa.Column("api_key_enc", sa.String(512), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("remote_id", sa.String(128)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("remote_status", sa.String(32)),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("query_failures", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(1024)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    for column in ("tenant_id", "task_id", "execution_id"):
        op.create_index("ix_ac_provider_job_" + column, "ac_provider_job", [column])
    op.create_index(
        "uq_provider_job_round",
        "ac_provider_job",
        ["tenant_id", "execution_id", "round"],
        unique=True,
    )


def downgrade() -> None:
    op.alter_column(
        "ac_asset", "url", existing_type=sa.String(8192), type_=sa.String(512)
    )
    op.drop_table("ac_provider_job")
    for table, name in (
        ("ac_asset", "uq_asset_provider_job"),
        ("ac_task_node_run", "uq_node_provider_job"),
    ):
        op.drop_index(name, table_name=table)
        op.drop_column(table, "provider_job_id")
    op.drop_index("ix_ac_task_execution_next_poll_at", table_name="ac_task_execution")
    for column in (
        "state_snapshot",
        "provider_snapshot_enc",
        "next_node",
        "in_flight_node",
        "next_poll_at",
    ):
        op.drop_column("ac_task_execution", column)
