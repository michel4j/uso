#!/bin/bash

set -ex
APP_DIRECTORY="/usonline"
export SERVER_NAME=${SERVER_NAME:-$(hostname -f)}

# Wait for Database
/wait-for-it.sh database:5432 -t 60

# Clear runtime contexts
rm -rf /var/run/apache2/* /tmp/apache2*

# Configure Apache
if [ -f /usonline/local/certs/server.key ] && [ -f /usonline/local/certs/server.crt ]; then
    # Disable chain cert if no ca.crt file available
    if [ -f /usonline/local/certs/ca.crt ]; then
        /bin/cp /usonline/deploy/apache/uso-ssl-chain.conf /etc/apache2/sites-enabled/999-usonline.conf
    else
        /bin/cp  /usonline/deploy/apache/uso-ssl.conf /etc/apache2/sites-enabled/999-usonline.conf
    fi
fi


# Make sure the local directory is a Python package
if [ ! -f ${APP_DIRECTORY}/local/__init__.py ]; then
    touch ${APP_DIRECTORY}/local/__init__.py
fi


# check of database exists and initialize it if not
for trial in {1..5}; do
    echo "Migrating database tables ... (attempt $trial)"
    /usonline/manage.py migrate --noinput && break
    sleep 5
done

if [ ! -f /usonline/local/.dbinit ]; then
    echo "Loading Pre-Application data ..."
    for f in /usonline/usonline/fixtures/pre/*.{yml,json,yaml}; do
      if [[ -e "$f" ]]; then
        /usonline/manage.py loaddata "$f" -v2
      fi
    done

    echo "Loading Application initial data ..."
    /usonline/manage.py loaddata initial-data -v2

    echo "Loading Post-Application data ..."
    for f in /usonline/usonline/fixtures/post/*.{yml,json,yaml}; do
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
fi

# Initialize Media Directory
MEDIA_ROOT="${APP_DIRECTORY}/local/media"
if [ ! -d "${MEDIA_ROOT}" ]; then
  mkdir -p "${MEDIA_ROOT}"
fi

# Update ownership to 'www-data' (Debian)
if [ ! -f "${MEDIA_ROOT}/.init" ]; then
    chown -R www-data:www-data "${MEDIA_ROOT}"
    touch "${MEDIA_ROOT}/.init"
fi

# Create log directory if missing
LOG_DIRECTORY="${APP_DIRECTORY}/local/logs"
if [ ! -d "${LOG_DIRECTORY}" ]; then
    mkdir -p "${LOG_DIRECTORY}"
fi

# Launch Debian's apache2 binary using its standard environment variables
# Debian's Apache requires variables like APACHE_RUN_DIR to be sourced first.
source /etc/apache2/envvars
exec /usr/sbin/apache2 -DFOREGROUND -e debug
