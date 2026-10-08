---
ID: 001
Origin: 001
UUID: a17c42d9
Status: Ready for QA
Target Release: None
Epic Alignment: Phase 1 PoC
Changelog:
  - 2026-10-08: Created plan and same-pass critique from confirmed scope.
   - 2026-10-08: Implementation started.
   - 2026-10-08: Implementation completed; Docker engine smoke test remains outstanding. See ../implementation/001-phase-one-leads-chatbot-implementation.md.
---

# Plan: Phase 1 Leads Chatbot PoC

## Value Statement

As someone evaluating the PoC, I want a runnable leads dashboard with a chat entry point, so that I can inspect the lead data and see where the later LangChain integration will live.

## Objective

Deliver the Phase 1 local Docker Compose application: a PostgreSQL database migrated and seeded from `backend/alembic/Leads.csv`, a FastAPI leads read endpoint, and a React leads table with a non-functional chat panel. LangGraph conversation behavior is Phase 2.

## Scope

In scope:
- Complete `.env.example`, Compose, and frontend/backend container setup so `docker compose up` works with documented local defaults.
- Create and seed a Leads table with all 17 source fields and 500 CSV records; use the verified unique `Lead Number` as the primary key and handle blank CSV values.
- Expose leads to the frontend through a read-only API endpoint.
- Replace the Vite starter screen with a responsive leads table. Keep scrolling within the leads table region; pin only the right-side action column while the table scrolls. Email, LinkedIn, and delete actions are visual placeholders and do not mutate data.
- Add a floating chat toggle and a non-functional chat panel with a disabled/placeholder composer.
- Document local startup and configuration.

Out of scope:
- LangChain or LangGraph runtime, prompt/model configuration, and message handling.
- Real email/LinkedIn actions, deletion, authentication, lead editing, search, and pagination.

## Assumptions

- The existing PostgreSQL service remains the database.
- All CSV fields are persisted; numeric and yes/no fields are mapped to suitable nullable database types, and blanks remain null.
- Compose interpolation defaults allow startup without requiring a local `.env`; `.env.example` documents the overridable variables.
- The frontend is served as a built static app and is configured to call the locally exposed backend API.
- No release roadmap or existing `agent-output/` plan chain was present.

## Plan

1. **Make the Compose stack runnable.** Align each Dockerfile with its actual project layout and package manager; build and serve the Vite output; configure database and API environment variables; add PostgreSQL health readiness and ensure migrations complete before the API serves requests. Keep host ports configurable/documented and provide safe local-only defaults.
   - Acceptance: a clean checkout can build and start database, backend, and frontend using `docker compose up`; the browser can reach the frontend and API; startup does not race database readiness.

2. **Add the Leads data model, migration, seed, and read API.** Configure Alembic from the runtime database URL and the model metadata. Create the table and import the CSV as part of the initial migration, preserving all source fields and handling quoted commas, numeric values, and blanks. Add a read-only endpoint returning the lead records in a frontend-friendly JSON shape, plus the required local CORS configuration.
   - Acceptance: migration creates the table and seeds all 500 records; `Lead Number` is the stable key; API reads return the stored records; downgrade removes the created table.

3. **Build the leads and chat UI.** Replace the starter content with a compact table view that loads records from the API and presents loading/error/empty states. Provide a bounded scroll container for the lead data, with the actions column sticky at the right edge and no other pinned action columns. Add dummy Email, LinkedIn, and delete buttons. Add a floating chat button that opens/closes a placeholder chat panel; message submission remains disabled.
   - Acceptance: table data is readable on desktop and narrow screens; table scrolling does not move the action column out of view; page chrome and actions are not part of the table scroll area; chat open/close works without implying a live assistant.

4. **Document and verify the local demo.** Update the root README with prerequisites, startup, available local URLs, configuration, and shutdown/reset guidance. Verify Compose build/start, migration and seed, API response, frontend build/lint, and the primary UI behavior.

## Validation

Use focused backend checks for model/migration/CSV import/API behavior, frontend lint and production build, and a clean Compose startup smoke check. Confirm the migration is repeatable through Alembic revision tracking and that a fresh database contains all 500 leads. No separate QA plan is included here.

## Risks

- CSV blanks and quoted categorical values need correct parsing and nullable conversion; otherwise migration can fail or silently change source data.
- Compose readiness and startup ordering must cover both database health and migration completion.
- A frontend static build cannot rely on runtime Vite environment substitution; API base URL must be provided at build time or served through a proxy.
- Local Compose defaults are for a PoC only and must not be represented as production secrets or deployment security.

## Critique

Flags:
- The existing backend Dockerfile refers to `requirements.txt` and `app.main`, while the repository uses `pyproject.toml`/`uv.lock` and root `main.py`; it also starts Uvicorn without a host binding. The frontend Dockerfile currently launches Vite after omitting dev dependencies and copies a `build/` path although Vite outputs `dist/`. Both need correction within infrastructure scope.
- The existing Alembic environment has a placeholder URL and no model metadata; database configuration, importable model metadata, and runtime migration ordering are necessary parts of the feature, not optional cleanup.
- The 17-column source can make the table wide. Preserve the fields and constrain scrolling to the table region; keep the action column sticky on the right as confirmed. Search, pagination, and other workflow features are intentionally excluded.
- The intended UI is a placeholder only: no mock conversational responses or send behavior should be added under the Phase 1 scope.

Recommendation: Go
Next: implementer
