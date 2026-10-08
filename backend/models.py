from sqlmodel import Field, SQLModel


class Lead(SQLModel, table=True):
    __tablename__ = "leads"

    lead_number: int = Field(primary_key=True)
    lead_origin: str | None = None
    lead_source: str | None = None
    do_not_email: bool | None = None
    do_not_call: bool | None = None
    converted: bool | None = None
    total_visits: int | None = None
    total_time_spent_on_website: int | None = None
    page_views_per_visit: float | None = None
    last_activity: str | None = None
    country: str | None = None
    specialization: str | None = None
    current_occupation: str | None = None
    lead_quality: str | None = None
    lead_profile: str | None = None
    city: str | None = None
    last_notable_activity: str | None = None