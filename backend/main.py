import os
from collections.abc import Iterator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlmodel import Session, create_engine, select

from chat import ChatUnavailableError, ask_leads_assistant, create_lifespan
from database import build_database_url
from models import Lead

engine = create_engine(build_database_url(), pool_pre_ping=True)

app = FastAPI(title="Leads API", lifespan=create_lifespan(engine))
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "FRONTEND_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
    ).split(","),
    allow_methods=["GET", "POST"],
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


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = Field(default=None, max_length=100)


class ChatResponse(BaseModel):
    reply: str
    thread_id: str


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    graph = getattr(request.app.state, "chat_graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="Chat assistant is not ready.")

    try:
        reply, thread_id = ask_leads_assistant(graph, payload.message, payload.thread_id)
    except ChatUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return ChatResponse(reply=reply, thread_id=thread_id)
