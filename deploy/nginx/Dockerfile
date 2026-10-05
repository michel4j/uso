FROM python:3.13-slim

COPY deploy/nginx/run-server.sh /
COPY deploy/nginx/health-check.sh /
COPY deploy/wait-for-it.sh /
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT="/venv"
ADD . /usonline

RUN set -ex && \
    apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev bash sed libmagic1 && \
    cd /usonline && \
    uv add gunicorn && \
    uv sync && \
    mkdir -p /usonline/local && \
    chmod -v +x /run-server.sh /wait-for-it.sh /health-check.sh && \
    sed -i -E 's@#!/usr/bin/env python@#!/venv/bin/python3@' /usonline/manage.py

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD /health-check.sh

EXPOSE 80
VOLUME ["/usonline/local", "/usonline/static"]

CMD ["/run-server.sh"]

