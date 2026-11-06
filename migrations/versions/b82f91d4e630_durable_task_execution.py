"""Durable task attempts, per-attempt output isolation and request deduplication.

Revision ID: b82f91d4e630
Revises: 7c4bb2de21ad
"""

import sqlalchemy as sa
from alembic import op

revision = "b82f91d4e630"
down_revision = "7c4bb2de21ad"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("ac_task", "ac_batch"):
        op.add_column(table, sa.Column("request_key", sa.String(128), nullable=True))
        op.add_column(table, sa.Column("request_hash", sa.String(64), nullable=True))
        op.create_index(
            "uq_" + table[3:] + "_request",
            table,
            ["tenant_id", "request_key"],
            unique=True,
        )
    op.add_column("ac_task", sa.Column("execution_id", sa.String(32), nullable=True))
    for table in ("ac_task_node_run", "ac_copy", "ac_asset", "ac_compliance_report"):
        op.add_column(table, sa.Column("execution_id", sa.String(32), nullable=True))
        op.create_index("ix_" + table + "_execution_id", table, ["execution_id"])
    op.create_table(
        "ac_task_execution",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("tenant_id", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(32)),
        sa.Column("updated_by", sa.String(32)),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.SmallInteger(), nullable=False),
        sa.Column("task_id", sa.String(32), nullable=False),
        sa.Column("request_key", sa.String(128)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.String(1024)),
    )
    for column in ("tenant_id", "task_id", "status"):
        op.create_index("ix_ac_task_execution_" + column, "ac_task_execution", [column])
    op.create_index(
        "uq_execution_request",
        "ac_task_execution",
        ["tenant_id", "task_id", "request_key"],
        unique=True,
    )
    op.create_index(
        "uq_task_execution_active",
        "ac_task_execution",
        ["tenant_id", "task_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running') AND is_deleted = 0"),
    )


def downgrade() -> None:
    op.drop_table("ac_task_execution")
    for table in ("ac_task_node_run", "ac_copy", "ac_asset", "ac_compliance_report"):
        op.drop_index("ix_" + table + "_execution_id", table_name=table)
        op.drop_column(table, "execution_id")
    op.drop_column("ac_task", "execution_id")
    for table in ("ac_task", "ac_batch"):
        op.drop_index("uq_" + table[3:] + "_request", table_name=table)
        op.drop_column(table, "request_hash")
        op.drop_column(table, "request_key")
