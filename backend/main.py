import os
from collections.abc import Iterator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, create_engine, select

from database import build_database_url
from models import Lead

engine = create_engine(build_database_url(), pool_pre_ping=True)

app = FastAPI(title="Leads API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "FRONTEND_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
    ).split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"message": "Leads API"}


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/leads", response_model=list[Lead])
def list_leads(session: Session = Depends(get_session)) -> list[Lead]:
    return list(session.exec(select(Lead).order_by(Lead.lead_number)).all())