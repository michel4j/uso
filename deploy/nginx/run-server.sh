#!/bin/bash

export SERVER_NAME=${SERVER_NAME:-$(hostname -f)}
export NUM_WORKERS=${NUM_WORKERS:-5}

./wait-for-it.sh database:5432 -t 60

APP_DIRECTORY="/usonline"


# Make sure the local directory is a Python package
if [ ! -f ${APP_DIRECTORY}/local/__init__.py ]; then
    touch ${APP_DIRECTORY}/local/__init__.py
fi

# check of database exists and initialize it if not
for trial in {1..5}; do
    echo "Migrating database tables ... (attempt $trial)"
    ${APP_DIRECTORY}/manage.py migrate --noinput && break
    sleep 5
done

if [ ! -f ${APP_DIRECTORY}/local/.dbinit ]; then
    echo "Loading initial data ..."
    ${APP_DIRECTORY}/manage.py loaddata initial-data &&

    # Create superuser if not already created
    if [ -n "${DJANGO_SUPERUSER_PASSWORD}" ] && [ -n "${DJANGO_SUPERUSER_USERNAME}" ]; then
        echo "Creating Superuser ..."
        ${APP_DIRECTORY}/manage.py createsuperuser --noinput
    fi

    # run cron jobs for the first time
    echo "Running initial background tasks ..."
    ${APP_DIRECTORY}/manage.py runcrons --force -v3

    if [ -d ${APP_DIRECTORY}/local/kickstart ]; then
        echo "Loading kickstart data ..."
        for f in "${APP_DIRECTORY}"/local/kickstart/*.{yml,json,yaml}; do
          if [[ -e "$f" ]]; then
            echo "Loading data from $f ..."
            ${APP_DIRECTORY}/manage.py loaddata "$f"
          fi
        done
    fi
    touch ${APP_DIRECTORY}/local/.dbinit
fi

# create log files
if [ -d ${APP_DIRECTORY}/local/logs ]; then
    touch ${APP_DIRECTORY}/local/logs/access.log
    touch ${APP_DIRECTORY}/local/logs/error.log
fi

# Launch the server
tail -n 0 -f ${APP_DIRECTORY}/local/logs/error.log &
exec /venv/bin/gunicorn usonline.wsgi:application \
    --pid /var/run/gunicorn/gunicorn.pid \
    --forwarded-allow-ips "*" \
    --pythonpath ${APP_DIRECTORY} \
    --name usonline \
    --bind unix:/var/run/gunicorn/gunicorn.sock \
    --workers "${NUM_WORKERS}" \
    --log-level=info \
    --log-file=${APP_DIRECTORY}/local/logs/error.log \
    --access-logfile=${APP_DIRECTORY}/local/logs/access.log \
"$@"
