"""engagements, snapshots, node.engagement_id

Revision ID: 24726b59aa26
Revises: 30c9b518252d
Create Date: 2026-08-01

Adds multi-engagement/workspace support (spec §7 Phase 6): the
`engagements` table, a nullable `engagement_id` FK on `nodes` (nullable so
pre-Phase-6 data doesn't need a backfill to stay valid — see
app/models/engagement.py's docstring for why "nullable, defaults to the
active engagement" was chosen over a hard NOT NULL + backfill), and the
`snapshots` table for point-in-time graph capture/diffing.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "24726b59aa26"
down_revision: Union[str, None] = "30c9b518252d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engagements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("client_name", sa.String(256), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.add_column(
        "nodes",
        sa.Column(
            "engagement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagements.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_nodes_engagement_id", "nodes", ["engagement_id"])

    op.create_table(
        "snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "engagement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(256), nullable=False),
        sa.Column("node_count", sa.Integer(), nullable=False),
        sa.Column("edge_count", sa.Integer(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_snapshots_engagement_id", "snapshots", ["engagement_id"])


def downgrade() -> None:
    op.drop_table("snapshots")
    op.drop_index("ix_nodes_engagement_id", table_name="nodes")
    op.drop_column("nodes", "engagement_id")
    op.drop_table("engagements")
