#!/bin/bash

export SERVER_NAME=${SERVER_NAME:-$(hostname -f)}
# Make sure we're not confused by old, incompletely-shutdown httpd
# context after restarting the container.  httpd won't start correctly
# if it thinks it is already running.
rm -rf /run/httpd/* /tmp/httpd*

# Configure Apache
if [ -f /usonline/local/certs/server.key ] && [ -f /usonline/local/certs/server.crt ]; then
    # Disable chain cert if no ca.crt file available
    if [ -f /usonline/local/certs/ca.crt ]; then
        /bin/cp /usonline/deploy/usonline-ssl-chain.conf /etc/apache2/conf.d/99-usonline.conf
    else
        /bin/cp /usonline/deploy/usonline-ssl.conf /etc/apache2/conf.d/99-usonline.conf
    fi
else
    /bin/cp /usonline/deploy/usonline.conf /etc/apache2/conf.d/99-usonline.conf
fi

./wait-for-it.sh database:5432 -t 60
# Make sure the local directory is a Python package
if [ ! -f /usonline/local/__init__.py ]; then
    touch /usonline/local/__init__.py
fi

# check of database exists and initialize it if not
if [ ! -f /usonline/local/.dbinit ]; then
    echo "Initializing database tables ..."
    for try in {1..5}; do
        /usonline/manage.py migrate --noinput && break
        sleep 5
    done
    /usonline/manage.py loaddata initial-data &&
    touch /usonline/local/.dbinit
    chown -R apache:apache /usonline/local/media

    # Create superuser if not already created
    if [ -n "${DJANGO_SUPERUSER_PASSWORD}" ] && [ -n "${DJANGO_SUPERUSER_USERNAME}" ] && [ -n "${DJANGO_SUPERUSER_EMAIL}" ]; then
        echo "Creating Superuser ..."
        /usonline/manage.py createsuperuser --noinput --email "${DJANGO_SUPERUSER_EMAIL}"
    fi

    if [ -d /usonline/local/kickstart ]; then
        echo "Loading kickstart data ..."
        for f in /usonline/local/kickstart/*.{yml,json,yaml}; do
          if [[ -e "$f" ]]; then
            echo "Loading data from $f ..."
            /usonline/manage.py loaddata "$f"
          fi
        done
    fi
else
    for trial in {1..5}; do
        echo "Migrating database tables ... (attempt $trial)"
        /usonline/manage.py migrate --noinput && break
        sleep 5
    done
fi

# create log directory if missing
if [ ! -d /usonline/local/logs ]; then
    mkdir -p /usonline/local/logs
fi

# Launch the server
exec /usr/sbin/httpd -DFOREGROUND -e debug
