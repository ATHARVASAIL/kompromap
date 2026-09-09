"""Fix list-typed columns to JSONB (was ARRAY in initial migration).

`StringList` TypeDecorator uses JSON as its impl, but the initial migration
created `tags`, `params`, and `tech_stack` as `ARRAY(String)`.  This
migration converts them to `JSONB` so the DB matches what SQLAlchemy
actually writes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "34_fix_list_columns_to_jsonb"
down_revision: Union[str, None] = "33_knowledge_base"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert ARRAY(String) columns to JSONB, coercing existing values.
    op.alter_column(
        "nodes",
        "tags",
        type_=postgresql.JSONB(),
        postgresql_using="tags::jsonb",
    )
    op.alter_column(
        "endpoints",
        "params",
        type_=postgresql.JSONB(),
        postgresql_using="params::jsonb",
    )
    op.alter_column(
        "services",
        "tech_stack",
        type_=postgresql.JSONB(),
        postgresql_using="tech_stack::jsonb",
    )
    op.alter_column(
        "web_applications",
        "tech_stack",
        type_=postgresql.JSONB(),
        postgresql_using="tech_stack::jsonb",
    )


def downgrade() -> None:
    # JSONB -> ARRAY(String)
    op.alter_column(
        "nodes",
        "tags",
        type_=postgresql.ARRAY(sa.String()),
        postgresql_using="tags::text[]",
    )
    op.alter_column(
        "endpoints",
        "params",
        type_=postgresql.ARRAY(sa.String()),
        postgresql_using="params::text[]",
    )
    op.alter_column(
        "services",
        "tech_stack",
        type_=postgresql.ARRAY(sa.String()),
        postgresql_using="tech_stack::text[]",
    )
    op.alter_column(
        "web_applications",
        "tech_stack",
        type_=postgresql.ARRAY(sa.String()),
        postgresql_using="tech_stack::text[]",
    )
