FROM python:3.11-alpine

LABEL maintainer="Kathryn Janzen <kathryn.janzen@lightsource.ca>"

COPY requirements.txt /
COPY deploy/run-server.sh /
COPY deploy/wait-for-it.sh /
ADD . /usonline


RUN set -ex && \
    apk add --no-cache --virtual libpq apache2-ssl apache2-mod-wsgi openssl bash sed py3-pip && \
    /usr/bin/python3 -m venv /venv && source /venv/bin/activate && \
    /venv/bin/pip3 install --no-cache-dir --upgrade pip && \
    /venv/bin/pip3 install --no-cache-dir -r /requirements.txt  && \
    mkdir -p /usonline/local && \
    chmod -v +x /run-server.sh /wait-for-it.sh && \
    sed -i -E 's@#!/usr/bin/env python@#!/venv/bin/python3@' /usonline/manage.py && \
    /usonline/manage.py collectstatic --noinput


EXPOSE 443 80
VOLUME ["/usonline/local"]
CMD ["/run-server.sh"]

