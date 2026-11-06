FROM node:22-alpine AS ui
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HOST=0.0.0.0 \
    PORT=8080

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/organiser ./organiser
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY --from=ui /src/dist ./frontend/dist

RUN useradd --create-home --uid 10001 organiser \
    && chown -R organiser:organiser /app
USER organiser

EXPOSE 8080
CMD ["python", "-m", "organiser"]

FROM runtime AS test

USER root
COPY backend/requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY docker-compose.yml ./docker-compose.yml
COPY backend/tests ./tests
RUN chown -R organiser:organiser /app
USER organiser

CMD ["pytest", "-q", "tests"]

# Default build is the API. The test runner stays an explicit target.
FROM runtime
