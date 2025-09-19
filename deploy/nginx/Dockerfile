FROM python:3.13-alpine

COPY requirements.txt /
COPY deploy/nginx/run-server.sh /
COPY deploy/nginx/health-check.sh /
COPY deploy/wait-for-it.sh /

ADD . /usonline

RUN set -ex && \
    apk add --no-cache --virtual libpq bash sed libmagic && \
    python3 -m venv /venv && source /venv/bin/activate && \
    pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r /requirements.txt  && \
    pip3 install --no-cache-dir --upgrade gunicorn && \
    mkdir -p /usonline/local && \
    chmod -v +x /run-server.sh /wait-for-it.sh /health-check.sh && \
    sed -i -E 's@#!/usr/bin/env python@#!/venv/bin/python3@' /usonline/manage.py

EXPOSE 80
VOLUME ["/usonline/local", "/usonline/static"]

CMD ["/run-server.sh"]

