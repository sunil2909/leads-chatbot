import os

from sqlalchemy.engine import URL, make_url


def build_database_url() -> URL:
    configured_url = os.getenv("DATABASE_URL")
    if configured_url:
        return make_url(configured_url)

    return URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("POSTGRES_USER", "user"),
        password=os.getenv("POSTGRES_PASSWORD", "local_dev_password"),
        host=os.getenv("DATABASE_HOST", "localhost"),
        port=int(os.getenv("DATABASE_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "leads_db"),
    )