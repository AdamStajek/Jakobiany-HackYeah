FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH" \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --no-cache

COPY src ./src
COPY data/krakow.sqlite3 ./data/krakow.sqlite3
COPY data/routes/city.sqlite3 ./routes/city.sqlite3
ENV ROUTE_GRAPH_PATH=/app/routes/city.sqlite3

RUN useradd --uid 10001 --create-home app
RUN chown -R app:app /app/data
ENV DATABASE_PATH=/app/data/krakow.sqlite3
VOLUME ["/app/data"]
USER app

EXPOSE 8000

CMD ["uvicorn", "hackyeah.main:app", "--host", "0.0.0.0", "--port", "8000"]
