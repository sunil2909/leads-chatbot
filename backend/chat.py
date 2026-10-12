"""LangGraph leads assistant.

Flow: user message -> agent (LLM + system prompt) -> optional `query_leads`
tool call against the database -> agent turns the tool result into a short
answer. Conversation history is kept per `thread_id` by the checkpointer.

FastAPI integration: `create_lifespan(engine)` builds the graph once at
startup and stores it on `app.state.chat_graph`; endpoints call
`ask_leads_assistant(graph, message, thread_id)`.
"""

import json
import os
import re
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import FastAPI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, StructuredTool
from langchain_ollama import ChatOllama
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from ollama import ResponseError
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from models import Lead

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "hf.co/MaziyarPanahi/Qwen3-1.7B-GGUF:Q6_K"
# agent -> tools -> agent counts as 3 steps; allow a couple of tool rounds.
RECURSION_LIMIT = 8
MAX_SAMPLE_LEADS = 20

TEXT_FILTERS = (
    "lead_origin",
    "lead_source",
    "country",
    "city",
    "specialization",
    "current_occupation",
    "lead_quality",
    "last_activity",
)
GROUPABLE_FIELDS = (*TEXT_FILTERS, "status")
LEAD_STATUSES = ("open", "closed")
EMPTY_VALUES = {"", "any", "all", "none", "null"}
SAMPLE_FIELDS = (
    "lead_number",
    "status",
    "lead_origin",
    "lead_source",
    "country",
    "city",
    "lead_quality",
    "created_at",
    "closed_at",
)

SYSTEM_PROMPT = """You answer questions about sales leads. Today is {today}.
- Always call `query_leads` first; never invent numbers. Counts come from `total_matching`.
- Pass every condition as a filter. "Last week" = 7 days, "last month" = 30.
- Reply in one or two short sentences, naming the filters used.
- Off-topic questions: say you only help with lead data."""
# Qwen3 soft switch: skips the slow thinking phase. The model sometimes emits
# a tool call inside the empty think block, which Ollama drops; the agent then
# retries that step once with thinking enabled.
NO_THINK_SWITCH = "\n/no_think"

THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


class ChatUnavailableError(RuntimeError):
    """The language model could not be reached or failed to answer."""


class LeadQuery(BaseModel):
    status: str | None = Field(
        default=None, description='Lead status: "open" or "closed".'
    )
    lead_origin: str | None = Field(
        default=None, description='How the lead arrived, e.g. "API", "Landing Page Submission".'
    )
    lead_source: str | None = Field(
        default=None, description='Marketing source, e.g. "Google", "Olark Chat", "Direct Traffic".'
    )
    country: str | None = Field(default=None, description='Country, e.g. "India".')
    city: str | None = Field(default=None, description='City, e.g. "Mumbai".')
    specialization: str | None = Field(default=None, description="Lead's specialization.")
    current_occupation: str | None = Field(
        default=None, description='Occupation, e.g. "Unemployed", "Working Professional".'
    )
    lead_quality: str | None = Field(
        default=None, description='Quality, e.g. "High in Relevance", "Low in Relevance".'
    )
    last_activity: str | None = Field(
        default=None, description='Last activity, e.g. "Email Opened".'
    )
    created_in_last_days: int | None = Field(
        default=None, ge=1, description="Only leads created within this many days."
    )
    closed_in_last_days: int | None = Field(
        default=None, ge=1, description="Only leads closed within this many days."
    )
    group_by: str | None = Field(
        default=None,
        description=f"Return counts per value of one field: {', '.join(GROUPABLE_FIELDS)}.",
    )
    limit: int = Field(
        default=0,
        ge=0,
        le=MAX_SAMPLE_LEADS,
        description="How many example leads to list. Only set when the user asks to see leads.",
    )


def _clean(value: str | None) -> str | None:
    if value is None or value.strip().lower() in EMPTY_VALUES:
        return None
    return value.strip()


def _serialize(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


def make_query_leads_tool(
    engine: Engine, now: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> BaseTool:
    """Build the single DB tool the agent may call."""

    def query_leads(**kwargs: Any) -> str:
        query = LeadQuery(**kwargs)
        filters: dict[str, Any] = {}
        conditions = []

        status = _clean(query.status)
        if status is not None:
            status = status.lower()
            if status not in LEAD_STATUSES:
                return json.dumps(
                    {"error": f"status must be one of {list(LEAD_STATUSES)}, got {status!r}"}
                )
            filters["status"] = status
            conditions.append(col(Lead.status) == status)

        for field_name in TEXT_FILTERS:
            value = _clean(getattr(query, field_name))
            if value is not None:
                filters[field_name] = value
                conditions.append(
                    func.lower(getattr(Lead, field_name)) == value.lower()
                )

        current_time = now()
        if query.created_in_last_days:
            filters["created_in_last_days"] = query.created_in_last_days
            conditions.append(
                col(Lead.created_at)
                >= current_time - timedelta(days=query.created_in_last_days)
            )
        if query.closed_in_last_days:
            filters["closed_in_last_days"] = query.closed_in_last_days
            conditions.append(col(Lead.status) == "closed")
            conditions.append(
                col(Lead.closed_at)
                >= current_time - timedelta(days=query.closed_in_last_days)
            )

        group_by = _clean(query.group_by)
        if group_by is not None and group_by not in GROUPABLE_FIELDS:
            return json.dumps(
                {"error": f"group_by must be one of {list(GROUPABLE_FIELDS)}, got {group_by!r}"}
            )

        with Session(engine) as session:
            total = session.exec(
                select(func.count()).select_from(Lead).where(*conditions)
            ).one()
            result: dict[str, Any] = {
                "summary": f"{total} leads match these filters.",
                "total_matching": total,
                "filters": filters,
            }

            if group_by is not None:
                group_column = getattr(Lead, group_by)
                rows = session.exec(
                    select(group_column, func.count())
                    .where(*conditions)
                    .group_by(group_column)
                    .order_by(func.count().desc())
                ).all()
                result["group_by"] = group_by
                result["groups"] = [
                    {"value": value, "count": count} for value, count in rows
                ]

            if query.limit:
                leads = session.exec(
                    select(Lead)
                    .where(*conditions)
                    .order_by(col(Lead.lead_number))
                    .limit(query.limit)
                ).all()
                result["sample_leads"] = [
                    {name: _serialize(getattr(lead, name)) for name in SAMPLE_FIELDS}
                    for lead in leads
                ]

        return json.dumps(result)

    return StructuredTool.from_function(
        func=query_leads,
        name="query_leads",
        description=(
            "Count, filter, and group sales leads in the database. All arguments "
            "are optional; with no arguments it counts every lead. Text filters "
            "are case-insensitive exact matches. Returns JSON with "
            "`total_matching`, optional `groups`, and `sample_leads` when `limit` is set."
        ),
        args_schema=LeadQuery,
    )


def create_chat_model() -> BaseChatModel:
    return ChatOllama(
        base_url=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
        model=os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        temperature=0,
    )


def build_chat_graph(
    engine: Engine,
    model: BaseChatModel,
    checkpointer: BaseCheckpointSaver | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> CompiledStateGraph:
    tools = [make_query_leads_tool(engine, now)]
    model_with_tools = model.bind_tools(tools)

    def agent(state: MessagesState) -> dict[str, list]:
        prompt = SYSTEM_PROMPT.format(today=now().date().isoformat())
        response = model_with_tools.invoke(
            [SystemMessage(prompt + NO_THINK_SWITCH), *state["messages"]]
        )
        if not response.tool_calls and not _final_text(response):
            response = model_with_tools.invoke(
                [SystemMessage(prompt), *state["messages"]]
            )
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer or InMemorySaver())


def _final_text(message: AIMessage) -> str:
    content = message.content
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return THINK_BLOCK.sub("", content).strip()


def ask_leads_assistant(
    graph: CompiledStateGraph, message: str, thread_id: str | None = None
) -> tuple[str, str]:
    """Run one user turn through the graph. Returns (reply, thread_id)."""
    thread_id = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}

    try:
        state = graph.invoke({"messages": [HumanMessage(message)]}, config)
    except GraphRecursionError:
        return "Sorry, I couldn't work that out. Please try rephrasing the question.", thread_id
    except (httpx.HTTPError, ConnectionError, ResponseError) as error:
        raise ChatUnavailableError("The language model is unavailable.") from error

    reply = _final_text(state["messages"][-1])
    return reply or "Sorry, I don't have an answer for that.", thread_id


def create_lifespan(engine: Engine) -> Callable[[FastAPI], Any]:
    """FastAPI lifespan that owns the chat graph for the app's lifetime."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.chat_graph = build_chat_graph(engine, create_chat_model())
        yield
        app.state.chat_graph = None

    return lifespan
