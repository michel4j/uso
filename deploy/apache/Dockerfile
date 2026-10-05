FROM python:3.13-slim

COPY deploy/apache/run-server.sh /
COPY deploy/wait-for-it.sh /
COPY deploy/nginx/health-check.sh /
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT="/venv"

ADD . /usonline

RUN set -ex && \
    apt-get update && \
    apt-get install -y --no-install-recommends bash sed libmagic1 apache2 libapache2-mod-wsgi-py3 && \
    rm -rf /var/lib/apt/lists/* && \
    cd /usonline && \
    uv sync && \
    mkdir -p /usonline/local && \
    chmod -v +x /run-server.sh /wait-for-it.sh /health-check.sh && \
    rm -f /etc/apache2/sites-enabled/000-default.conf && \
    /bin/cp  /usonline/deploy/apache/uso.conf /etc/apache2/sites-enabled/999-usonline.conf && \
    sed -i -E 's@#!/usr/bin/env python@#!/venv/bin/python3@' /usonline/manage.py && \
    /usonline/manage.py collectstatic --noinput

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost/ || exit 1

EXPOSE 443 80
VOLUME ["/usonline/local"]
CMD ["/run-server.sh"]

