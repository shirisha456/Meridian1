FROM python:3.12-slim

WORKDIR /app

# libs/events installed as its own layer/step (see pyproject.toml's
# comment on why it's not a declared dependency) — this build's context
# is the repo root specifically so this path is reachable.
COPY libs/events /libs/events
RUN pip install --no-cache-dir /libs/events

COPY apps/core-api/pyproject.toml ./pyproject.toml
COPY apps/core-api/app ./app
RUN pip install --no-cache-dir .

COPY apps/core-api/alembic.ini ./
COPY apps/core-api/alembic ./alembic

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
