"""Add lead status and lifecycle dates.

The source CSV has no status or dates, so existing rows are backfilled
deterministically: converted leads are "closed", the rest are "open", and
dates are spread over the 90 days before the migration runs so that
time-based questions ("closed in the last week") have data to answer.
"""

from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from alembic import op

revision = "002_add_lead_status_and_dates"
down_revision = "001_create_leads"
branch_labels = None
depends_on = None

BACKFILL_WINDOW_DAYS = 90


def backfill_dates(
    lead_number: int, converted: bool, anchor: datetime
) -> tuple[str, datetime, datetime | None]:
    created_at = anchor - timedelta(
        days=(lead_number * 7919) % BACKFILL_WINDOW_DAYS,
        hours=lead_number % 24,
    )
    if not converted:
        return "open", created_at, None

    closed_at = min(created_at + timedelta(days=(lead_number * 31) % 21), anchor)
    return "closed", created_at, closed_at


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(), nullable=False, server_default="open")
        )
        batch_op.add_column(
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index("ix_leads_status", ["status"])

    leads = sa.table(
        "leads",
        sa.column("lead_number", sa.Integer()),
        sa.column("converted", sa.Boolean()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("closed_at", sa.DateTime(timezone=True)),
    )
    connection = op.get_bind()
    anchor = datetime.now(UTC).replace(microsecond=0)
    rows = connection.execute(sa.select(leads.c.lead_number, leads.c.converted)).all()

    for lead_number, converted in rows:
        status, created_at, closed_at = backfill_dates(
            lead_number, bool(converted), anchor
        )
        connection.execute(
            leads.update()
            .where(leads.c.lead_number == lead_number)
            .values(status=status, created_at=created_at, closed_at=closed_at)
        )


def downgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.drop_index("ix_leads_status")
        batch_op.drop_column("closed_at")
        batch_op.drop_column("created_at")
        batch_op.drop_column("status")
