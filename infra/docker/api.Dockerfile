# syntax=docker/dockerfile:1
# The API: FastAPI and the fraudml package, served by uvicorn. Build from the repository root:
#   docker build -f infra/docker/api.Dockerfile -t fraud-risk-api .
# Models, uploads and the business rules live in the /data volume, never in the image.
ARG PYTHON_IMAGE=python:3.11-slim-bookworm

FROM ${PYTHON_IMAGE} AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH
WORKDIR /src
# Third-party packages first, from the two pyproject files alone: a code change reuses this
# large layer, so a new release is a small download.
COPY ml/pyproject.toml ml/
COPY backend/pyproject.toml backend/
RUN python -c 'import tomllib; [print(d) for f in ("ml", "backend") for d in tomllib.load(open(f"{f}/pyproject.toml", "rb"))["project"]["dependencies"] if d != "fraudml"]' > requirements.txt \
 && pip install -r requirements.txt
COPY ml/fraudml ml/fraudml
COPY backend/app backend/app
RUN pip wheel --no-deps --wheel-dir /wheels ./ml ./backend

FROM ${PYTHON_IMAGE}
# LightGBM needs the OpenMP runtime.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 10001 --create-home app \
 && mkdir /data \
 && chown app:app /data
COPY --from=build /venv /venv
RUN --mount=type=bind,from=build,source=/wheels,target=/wheels \
    /venv/bin/pip install --no-deps --no-cache-dir --disable-pip-version-check /wheels/*.whl
WORKDIR /app
COPY backend/alembic.ini backend/alembic.ini
COPY backend/alembic backend/alembic
COPY --chmod=755 infra/docker/api-entrypoint.sh /usr/local/bin/api-entrypoint
COPY --chmod=755 infra/docker/seed.sh /usr/local/bin/seed
ENV PATH=/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MODEL_DIR=/data/models \
    UPLOAD_DIR=/data/uploads \
    RULES_PATH=/data/business_rules.txt \
    WEB_CONCURRENCY=2
USER app
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"]
ENTRYPOINT ["api-entrypoint"]
CMD ["serve"]
