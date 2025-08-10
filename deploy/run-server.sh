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
        /bin/cp  /usonline/deploy/usonline-ssl.conf /etc/apache2/conf.d/99-usonline.conf
    fi
else
    /bin/cp  /usonline/deploy/usonline.conf /etc/apache2/conf.d/99-usonline.conf
fi

./wait-for-it.sh database:5432 -t 60
# Make sure the local directory is a Python package
if [ ! -f /usonline/local/__init__.py ]; then
    touch /usonline/local/__init__.py
fi

# check of database exists and initialize it if not
for trial in {1..5}; do
    echo "Migrating database tables ... (attempt $trial)"
    /usonline/manage.py migrate --noinput && break
    sleep 5
done

if [ ! -f /usonline/local/.dbinit ]; then
    echo "Loading Pre-Application data ..."
    for f in /usonline/fixtures/pre/*.{yml,json,yaml}; do
      if [[ -e "$f" ]]; then
        /usonline/manage.py loaddata "$f" -v2
      fi
    done

    echo "Loading Application initial data ..."
    /usonline/manage.py loaddata initial-data -v2 &&

    echo "Loading Post-Application data ..."
    for f in /usonline/fixtures/*.{yml,json,yaml}; do
      if [[ -e "$f" ]]; then
        /usonline/manage.py loaddata "$f" -v2
      fi
    done

    # Create superuser if not already created
    if [ -n "${DJANGO_SUPERUSER_PASSWORD}" ] && [ -n "${DJANGO_SUPERUSER_USERNAME}" ]; then
        echo "Creating Superuser ..."
        /usonline/manage.py createsuperuser --noinput
    fi

    # run cron jobs for the first time
    echo "Running initial background tasks ..."
    /usonline/manage.py runcrons --force -v3

    if [ -d /usonline/local/kickstart ]; then
        echo "Loading kickstart data ..."
        for f in /usonline/local/kickstart/*.{yml,json,yaml}; do
          if [[ -e "$f" ]]; then
            echo "Loading data from $f ..."
            /usonline/manage.py loaddata "$f"
          fi
        done
    fi
    touch /usonline/local/.dbinit
    chown -R apache:apache /usonline/local/media
fi

# create log directory if missing
if [ ! -d /usonline/local/logs ]; then
    mkdir -p /usonline/local/logs
fi

# Launch the server
exec /usr/sbin/httpd -DFOREGROUND -e debug
