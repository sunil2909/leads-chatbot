import json
import os
import re
import unittest
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from chat import (
    NO_THINK_SWITCH,
    SYSTEM_PROMPT,
    ask_leads_assistant,
    build_chat_graph,
    create_chat_model,
    make_query_leads_tool,
)
from main import app
from models import Lead

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def days_ago(days: int) -> datetime:
    return NOW - timedelta(days=days)


# 4 open leads, 5 closed leads: 2 closed in the last week, 3 closed earlier.
SCENARIO_LEADS = [
    dict(lead_number=1, status="open", lead_source="Google", country="India", city="Mumbai", created_at=days_ago(2)),
    dict(lead_number=2, status="open", lead_source="Google", country="India", city="Thane", created_at=days_ago(20)),
    dict(lead_number=3, status="open", lead_source="Olark Chat", country="India", city="Mumbai", created_at=days_ago(3)),
    dict(lead_number=4, status="open", lead_source="Direct Traffic", country="United States", created_at=days_ago(40)),
    dict(lead_number=5, status="closed", converted=True, lead_source="Google", country="India", created_at=days_ago(10), closed_at=days_ago(1)),
    dict(lead_number=6, status="closed", converted=True, lead_source="Reference", country="India", created_at=days_ago(15), closed_at=days_ago(6)),
    dict(lead_number=7, status="closed", converted=True, lead_source="Google", country="India", created_at=days_ago(30), closed_at=days_ago(8)),
    dict(lead_number=8, status="closed", converted=True, lead_source="Olark Chat", country="India", created_at=days_ago(45), closed_at=days_ago(20)),
    dict(lead_number=9, status="closed", converted=True, lead_source="Direct Traffic", country="United States", created_at=days_ago(60), closed_at=days_ago(35)),
]


def create_scenario_engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(Lead(**lead) for lead in SCENARIO_LEADS)
        session.commit()
    return engine


class ScriptedChatModel(GenericFakeChatModel):
    """Fake LLM that replays scripted AI messages and accepts bound tools."""

    def bind_tools(self, tools, **kwargs):
        return self


def tool_call(args: dict, call_id: str = "call_1") -> AIMessage:
    return AIMessage(
        content="", tool_calls=[{"name": "query_leads", "args": args, "id": call_id}]
    )


class QueryLeadsToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_scenario_engine()
        cls.tool = make_query_leads_tool(cls.engine, now=lambda: NOW)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def query(self, **args) -> dict:
        return json.loads(self.tool.invoke(args))

    def test_counts_all_leads_without_filters(self):
        self.assertEqual(self.query()["total_matching"], 9)

    def test_how_many_leads_are_open(self):
        self.assertEqual(self.query(status="open")["total_matching"], 4)

    def test_how_many_leads_were_closed_in_the_last_week(self):
        result = self.query(closed_in_last_days=7, limit=5)

        self.assertEqual(result["total_matching"], 2)
        self.assertEqual(
            {lead["lead_number"] for lead in result["sample_leads"]}, {5, 6}
        )

    def test_how_many_leads_were_closed_in_the_last_month(self):
        self.assertEqual(self.query(closed_in_last_days=30)["total_matching"], 4)

    def test_how_many_new_leads_this_week(self):
        self.assertEqual(self.query(created_in_last_days=7)["total_matching"], 2)

    def test_text_filters_are_case_insensitive(self):
        result = self.query(status="OPEN", lead_source="google", city="mumbai")

        self.assertEqual(result["total_matching"], 1)
        self.assertEqual(result["filters"]["status"], "open")

    def test_open_leads_by_source_breakdown(self):
        result = self.query(status="open", group_by="lead_source")

        groups = {group["value"]: group["count"] for group in result["groups"]}
        self.assertEqual(groups, {"Google": 2, "Olark Chat": 1, "Direct Traffic": 1})

    def test_placeholder_values_from_the_model_are_ignored(self):
        self.assertEqual(
            self.query(status="any", country="", city="null")["total_matching"], 9
        )

    def test_invalid_status_returns_error_for_the_model(self):
        self.assertIn("error", self.query(status="pending"))

    def test_invalid_group_by_returns_error_for_the_model(self):
        self.assertIn("error", self.query(group_by="email"))

    def test_limit_controls_sample_size(self):
        self.assertEqual(len(self.query(limit=3)["sample_leads"]), 3)
        self.assertNotIn("sample_leads", self.query())


class ChatGraphTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_scenario_engine()

    def tearDown(self):
        self.engine.dispose()

    def build_graph(self, *messages: AIMessage):
        model = ScriptedChatModel(messages=iter(messages))
        return build_chat_graph(self.engine, model, now=lambda: NOW)

    def test_open_leads_question_runs_tool_then_answers(self):
        graph = self.build_graph(
            tool_call({"status": "open"}), AIMessage("There are 4 open leads.")
        )

        reply, thread_id = ask_leads_assistant(graph, "How many leads are open?")

        self.assertEqual(reply, "There are 4 open leads.")
        state = graph.get_state({"configurable": {"thread_id": thread_id}}).values
        tool_messages = [m for m in state["messages"] if isinstance(m, ToolMessage)]
        self.assertEqual(len(tool_messages), 1)
        self.assertEqual(json.loads(tool_messages[0].content)["total_matching"], 4)

    def test_closed_last_week_question_runs_tool_then_answers(self):
        graph = self.build_graph(
            tool_call({"closed_in_last_days": 7}),
            AIMessage("2 leads were closed in the last 7 days."),
        )

        reply, thread_id = ask_leads_assistant(
            graph, "How many leads were closed in the last week?"
        )

        self.assertEqual(reply, "2 leads were closed in the last 7 days.")
        state = graph.get_state({"configurable": {"thread_id": thread_id}}).values
        tool_result = json.loads(state["messages"][2].content)
        self.assertEqual(tool_result["total_matching"], 2)

    def test_non_lead_question_answers_without_tool(self):
        graph = self.build_graph(AIMessage("I can only help with lead data."))

        reply, thread_id = ask_leads_assistant(graph, "What's the weather?")

        self.assertEqual(reply, "I can only help with lead data.")
        state = graph.get_state({"configurable": {"thread_id": thread_id}}).values
        self.assertEqual(len(state["messages"]), 2)

    def test_conversation_history_is_kept_per_thread(self):
        graph = self.build_graph(
            tool_call({"status": "open"}),
            AIMessage("There are 4 open leads."),
            tool_call({"status": "open", "lead_source": "Google"}, "call_2"),
            AIMessage("2 of them came from Google."),
        )

        _, thread_id = ask_leads_assistant(graph, "How many leads are open?")
        reply, same_thread = ask_leads_assistant(
            graph, "How many of those came from Google?", thread_id
        )

        self.assertEqual(same_thread, thread_id)
        self.assertEqual(reply, "2 of them came from Google.")
        state = graph.get_state({"configurable": {"thread_id": thread_id}}).values
        self.assertEqual(len(state["messages"]), 8)

    def test_empty_fast_response_is_retried_with_thinking(self):
        graph = self.build_graph(
            AIMessage(""),
            tool_call({"status": "open", "lead_source": "Google"}),
            AIMessage("2 open leads came from Google."),
        )

        reply, _ = ask_leads_assistant(graph, "How many open leads came from Google?")

        self.assertEqual(reply, "2 open leads came from Google.")

    def test_thinking_blocks_are_stripped_from_reply(self):
        graph = self.build_graph(
            AIMessage("<think>\nthe user greets me\n</think>\n\nHello! Ask me about leads.")
        )

        reply, _ = ask_leads_assistant(graph, "hi")

        self.assertEqual(reply, "Hello! Ask me about leads.")

    def test_endless_tool_loop_returns_fallback_reply(self):
        graph = self.build_graph(
            *(tool_call({"status": "open"}, f"call_{index}") for index in range(10))
        )

        reply, _ = ask_leads_assistant(graph, "How many leads are open?")

        self.assertIn("rephrasing", reply)


class RecordingChatModel(ScriptedChatModel):
    """Scripted fake LLM that also records the messages of every call."""

    calls: list = []

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(messages)
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


class SystemPromptTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_scenario_engine()

    def tearDown(self):
        self.engine.dispose()

    def run_graph(self, *messages: AIMessage) -> RecordingChatModel:
        model = RecordingChatModel(messages=iter(messages))
        graph = build_chat_graph(self.engine, model, now=lambda: NOW)
        ask_leads_assistant(graph, "How many leads are open?")
        return model

    def test_prompt_renders_today_and_keeps_core_rules(self):
        prompt = SYSTEM_PROMPT.format(today="2026-10-09")

        self.assertIn("Today is 2026-10-09.", prompt)
        for rule in ("query_leads", "total_matching", "7 days", "30", "only help with lead data"):
            self.assertIn(rule, prompt)

    def test_prompt_stays_small(self):
        prompt = SYSTEM_PROMPT.format(today="2026-10-09")

        self.assertLessEqual(len(prompt.splitlines()), 5)
        self.assertLess(len(prompt), 400)

    def test_agent_sends_prompt_with_no_think_switch(self):
        model = self.run_graph(AIMessage("There are 4 open leads."))

        first = model.calls[0][0]
        self.assertIsInstance(first, SystemMessage)
        self.assertEqual(
            first.content,
            SYSTEM_PROMPT.format(today=NOW.date().isoformat()) + NO_THINK_SWITCH,
        )

    def test_empty_reply_retries_with_plain_prompt(self):
        model = self.run_graph(
            AIMessage("<think>\n\n</think>"), AIMessage("There are 4 open leads.")
        )

        self.assertEqual(len(model.calls), 2)
        retry = model.calls[1][0]
        self.assertIsInstance(retry, SystemMessage)
        self.assertEqual(retry.content, SYSTEM_PROMPT.format(today=NOW.date().isoformat()))


class ChatEndpointTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_scenario_engine()
        model = ScriptedChatModel(
            messages=iter([tool_call({"status": "open"}), AIMessage("There are 4 open leads.")])
        )
        app.state.chat_graph = build_chat_graph(self.engine, model, now=lambda: NOW)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.state.chat_graph = None
        self.engine.dispose()

    def test_chat_endpoint_returns_reply_and_thread_id(self):
        response = self.client.post("/api/chat", json={"message": "How many leads are open?"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reply"], "There are 4 open leads.")
        self.assertTrue(response.json()["thread_id"])

    def test_chat_endpoint_rejects_empty_message(self):
        response = self.client.post("/api/chat", json={"message": ""})

        self.assertEqual(response.status_code, 422)

    def test_chat_endpoint_is_unavailable_before_startup(self):
        app.state.chat_graph = None

        response = self.client.post("/api/chat", json={"message": "hi"})

        self.assertEqual(response.status_code, 503)


@unittest.skipUnless(
    os.getenv("RUN_OLLAMA_TESTS") == "1",
    "Set RUN_OLLAMA_TESTS=1 (and OLLAMA_BASE_URL) to run against the real model.",
)
class LiveModelScenarioTests(unittest.TestCase):
    """Real usage questions answered by the configured Ollama model."""

    @classmethod
    def setUpClass(cls):
        cls.engine = create_scenario_engine()
        cls.graph = build_chat_graph(cls.engine, create_chat_model(), now=lambda: NOW)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def ask(self, question: str) -> str:
        reply, _ = ask_leads_assistant(self.graph, question)
        return reply

    def assertMentionsNumber(self, reply: str, number: int):
        words = {4: "four", 2: "two", 9: "nine"}
        pattern = rf"\b({number}|{words.get(number, number)})\b"
        self.assertRegex(reply.lower(), pattern, msg=reply)

    def test_how_many_leads_are_open(self):
        self.assertMentionsNumber(self.ask("How many leads are open?"), 4)

    def test_how_many_leads_were_closed_in_the_last_week(self):
        self.assertMentionsNumber(
            self.ask("How many leads were closed in the last week?"), 2
        )

    def test_how_many_leads_are_there_in_total(self):
        self.assertMentionsNumber(self.ask("How many leads do we have in total?"), 9)

    def test_how_many_open_leads_came_from_google(self):
        self.assertMentionsNumber(self.ask("How many open leads came from Google?"), 2)

    def test_unrelated_question_is_declined(self):
        reply = self.ask("Write me a poem about the sea.")
        self.assertTrue(re.search(r"lead", reply, re.IGNORECASE), msg=reply)


if __name__ == "__main__":
    unittest.main()
