FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv \
    && useradd --create-home --uid 10001 appuser

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

USER appuser

EXPOSE 8080

CMD ["sh", "-c", "uv run python -m alembic upgrade head && uv run python -m uvicorn main:app --host 0.0.0.0 --port 8080"]
