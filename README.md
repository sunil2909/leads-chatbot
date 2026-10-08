# Leadline PoC

A local leads dashboard PoC with a placeholder chat panel. The chat interface is not connected to LangChain or LangGraph yet; that integration is planned for Phase 2.

## Run Locally

Prerequisites: Docker Desktop with its Linux engine running and Docker Compose v2.

The Compose file has local defaults, so the stack can be started directly:

```powershell
docker compose up --build
```

To override ports or database settings, copy `.env.example` to `.env` and edit the values before starting. `VITE_API_URL` is embedded in the frontend at build time; rebuild the frontend after changing it.

- Dashboard: http://localhost:8000
- Leads API: http://localhost:8080/api/leads
- API documentation: http://localhost:8080/docs

The backend waits for PostgreSQL, applies Alembic migrations, and seeds the 500 rows from `backend/alembic/Leads.csv` before serving requests. PostgreSQL data is kept in a named Docker volume. `docker compose down` stops the services without deleting that data. To reset the database and reseed it, run `docker compose down -v`; this removes the named volume and its contents.

Email, LinkedIn, and delete controls are visual placeholders. The chat panel opens and displays a Phase 2 placeholder, but message sending and assistant responses are disabled.

