FROM python:3.12-alpine

COPY requirements.txt /
COPY deploy/apache/run-server.sh /
COPY deploy/wait-for-it.sh /
ADD . /usonline

RUN set -ex && \
    apk add --no-cache --virtual curl libpq apache2-ssl apache2-mod-wsgi openssl bash sed libmagic py3-pip && \
    echo $(python3 --version) && \
    python3 -m venv /venv && source /venv/bin/activate && \
    pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r /requirements.txt  && \
    mkdir -p /usonline/local && \
    chmod -v +x /run-server.sh /wait-for-it.sh && \
    sed -i -E 's@#!/usr/bin/env python@#!/venv/bin/python3@' /usonline/manage.py && \
    /usonline/manage.py collectstatic --noinput

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost/ || exit 1

EXPOSE 443 80
VOLUME ["/usonline/local"]
CMD ["/run-server.sh"]

