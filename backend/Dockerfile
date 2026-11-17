# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.9.30 /uv /uvx /bin/
RUN apt-get update \
    && apt-get -y upgrade \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/srv/.venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /srv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

ARG INSTALL_STRIX=false
ARG TARGETARCH=amd64
RUN if [ "$INSTALL_STRIX" = "true" ]; then \
      case "$TARGETARCH" in \
        amd64) wheel="strix_agent-1.7.1-py3-none-manylinux_2_17_x86_64.whl" ;; \
        arm64) wheel="strix_agent-1.7.1-py3-none-manylinux_2_17_aarch64.whl" ;; \
        *) echo "unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
      esac; \
      uv pip install --python /srv/.venv/bin/python \
        "https://github.com/usestrix/strix/releases/download/v1.7.1/$wheel"; \
    fi

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

RUN useradd --uid 10001 --create-home app \
    && mkdir -p /srv/var/artifacts /srv/var/strix_runs \
    && chown -R app:app /srv
USER app

EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
