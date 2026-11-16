# syntax=docker/dockerfile:1
FROM python:3.12-slim

RUN apt-get update \
    && apt-get -y upgrade \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN pip install --no-cache-dir "fastapi==0.163.1" "uvicorn[standard]==0.38.0" "starlette==1.10.0"

WORKDIR /srv
COPY app ./app

RUN useradd --uid 10001 --create-home lab
USER lab
EXPOSE 8099
HEALTHCHECK --interval=20s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8099/health',timeout=3)"
CMD ["uvicorn", "app.main:APP", "--host", "0.0.0.0", "--port", "8099"]
