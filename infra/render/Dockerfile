# syntax=docker/dockerfile:1
# The whole app in one container for Render's free tier (render.yaml): nginx serves the dashboard
# and forwards /api to one uvicorn worker on 127.0.0.1. Free services have no disk and only
# 0.1 CPU, so the synthetic months and a model trained on them are baked in at build time;
# PostgreSQL is Render's. Build from the repository root:
#   docker build -f infra/render/Dockerfile -t fraud-risk-render .
ARG PYTHON_IMAGE=python:3.11-slim-bookworm
ARG NODE_IMAGE=node:22-bookworm-slim

FROM ${NODE_IMAGE} AS web
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM ${PYTHON_IMAGE} AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*
RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH
WORKDIR /src
COPY ml/pyproject.toml ml/
COPY backend/pyproject.toml backend/
RUN python -c 'import tomllib; [print(d) for f in ("ml", "backend") for d in tomllib.load(open(f"{f}/pyproject.toml", "rb"))["project"]["dependencies"] if d != "fraudml"]' > requirements.txt \
 && pip install -r requirements.txt
COPY ml/fraudml ml/fraudml
COPY backend/app backend/app
RUN pip install --no-deps ./ml ./backend
# The demo data and its model. The empty folder makes the version number unique to this build
# (the trainer picks one past the highest model_vN): the registry pins each version's checksum,
# so a rebuilt model must not reuse a version the database has already seen.
ARG DEMO_ROWS=2000
RUN fraudml demo-data --out /opt/demo --rows "${DEMO_ROWS}" >/dev/null \
 && fraudml label --rules /opt/demo/business_rules.txt --out /tmp/processed \
      --month-dir /opt/demo/raw/202606 --month-dir /opt/demo/raw/202607 --month-dir /opt/demo/raw/202608 >/dev/null \
 && stamp="model_v$(date -u +%y%m%d%H%M)" \
 && mkdir -p "/opt/models/$stamp" \
 && fraudml train --processed /tmp/processed --out /opt/models \
 && rmdir "/opt/models/$stamp" \
 && rm -rf /tmp/processed

FROM ${PYTHON_IMAGE}
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 nginx \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 10001 --create-home app \
 && mkdir /data \
 && chown app:app /data
COPY --from=build /venv /venv
COPY --from=build --chown=app:app /opt/demo /opt/demo
COPY --from=build --chown=app:app /opt/models /opt/models
COPY --from=web /src/dist /usr/share/nginx/html
WORKDIR /app
COPY backend/alembic.ini backend/alembic.ini
COPY backend/alembic backend/alembic
COPY infra/nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY infra/render/nginx.conf /app/nginx.conf
COPY --chmod=755 infra/render/start.sh /usr/local/bin/start
# A checkout on Windows may have given the script CRLF line endings, which sh cannot run.
RUN sed -i 's/\r$//' /usr/local/bin/start /app/nginx.conf
ENV PATH=/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MODEL_DIR=/opt/models \
    UPLOAD_DIR=/data/uploads \
    RULES_PATH=/opt/demo/business_rules.txt \
    WEB_CONCURRENCY=1 \
    PORT=10000
USER app
EXPOSE 10000
CMD ["start"]
