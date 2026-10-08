"""Create and seed the leads table."""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

from seed_data import read_leads_csv

revision = "001_create_leads"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    leads_table = op.create_table(
        "leads",
        sa.Column("lead_number", sa.Integer(), nullable=False),
        sa.Column("lead_origin", sa.String(), nullable=True),
        sa.Column("lead_source", sa.String(), nullable=True),
        sa.Column("do_not_email", sa.Boolean(), nullable=True),
        sa.Column("do_not_call", sa.Boolean(), nullable=True),
        sa.Column("converted", sa.Boolean(), nullable=True),
        sa.Column("total_visits", sa.Integer(), nullable=True),
        sa.Column("total_time_spent_on_website", sa.Integer(), nullable=True),
        sa.Column("page_views_per_visit", sa.Float(), nullable=True),
        sa.Column("last_activity", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("specialization", sa.String(), nullable=True),
        sa.Column("current_occupation", sa.String(), nullable=True),
        sa.Column("lead_quality", sa.String(), nullable=True),
        sa.Column("lead_profile", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("last_notable_activity", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("lead_number", name="pk_leads"),
    )
    csv_path = Path(__file__).resolve().parents[1] / "Leads.csv"
    op.bulk_insert(leads_table, read_leads_csv(csv_path))


def downgrade() -> None:
    op.drop_table("leads")