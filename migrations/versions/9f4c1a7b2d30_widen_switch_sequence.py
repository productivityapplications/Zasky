# ruff: noqa
"""widen switch event sequence

Revision ID: 9f4c1a7b2d30
Revises: 6823aaca3872
Create Date: 2026-11-07 08:45:00.000000

Switch sequence numbers can exceed signed 32-bit INTEGER. Postgres must store
the durable cursor and processed-event keys as BIGINT; SQLite INTEGER already
supports 64-bit values.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f4c1a7b2d30"
down_revision: Union[str, Sequence[str], None] = "6823aaca3872"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _alter_sequence_columns(
    *, existing: type[sa.Integer] | type[sa.BigInteger], target: type[sa.Integer] | type[sa.BigInteger]
) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "switch_connection_state",
            "highest_processed_sequence",
            existing_type=existing(),
            type_=target(),
            existing_nullable=False,
        )
        op.alter_column(
            "processed_switch_events",
            "event_sequence",
            existing_type=existing(),
            type_=target(),
            existing_nullable=False,
        )
        return
    # SQLite stores both INTEGER and BIGINT as 64-bit INTEGER, but Alembic's
    # batch migration keeps the declared schema aligned with the models.
    with op.batch_alter_table("switch_connection_state") as batch_op:
        batch_op.alter_column(
            "highest_processed_sequence",
            existing_type=existing(),
            type_=target(),
            existing_nullable=False,
        )
    with op.batch_alter_table("processed_switch_events") as batch_op:
        batch_op.alter_column(
            "event_sequence",
            existing_type=existing(),
            type_=target(),
            existing_nullable=False,
        )


def upgrade() -> None:
    """Upgrade schema."""
    _alter_sequence_columns(existing=sa.Integer, target=sa.BigInteger)


def downgrade() -> None:
    """Downgrade schema."""
    _alter_sequence_columns(existing=sa.BigInteger, target=sa.Integer)
