#!/bin/bash

set -e

SCRIPT_NAME="$0"

SCRIPT_DIR="$(dirname $SCRIPT_NAME)"
USONLINE_DIR="$(dirname $SCRIPT_DIR)"

if [ -d "$USONLINE_DIR/local" ]; then
  echo "The directory '$USONLINE_DIR/local' already exists. Exiting."
  exit 1
else
  mkdir -p "$USONLINE_DIR/local"
  echo "Created directory '$USONLINE_DIR/local'."
fi

# Create directory structure
mkdir -p "$USONLINE_DIR/local/kickstart" &&
mkdir -p "$USONLINE_DIR/local/media/css" &&
mkdir -p "$USONLINE_DIR/local/logs" &&
mkdir -p "$USONLINE_DIR/local/database"

# Copy configuration files
DB_PASSWORD=$(openssl rand -base64 32 | tr -d '\n="`')
SECRET_KEY=$(openssl rand -base64 64 | tr -d '\n="`')
cp "${SCRIPT_DIR}/settings_template.py" "$USONLINE_DIR/local/settings.py" &&
cp "${SCRIPT_DIR}/custom.css" "$USONLINE_DIR/local/media/css/" &&
cp "${SCRIPT_DIR}/docker-compose-dev.yml" "$USONLINE_DIR/local/docker-compose.yml" &&

cat <<EOF > "$USONLINE_DIR/local/.env"
SECRET_KEY='${SECRET_KEY}'

DATABASE_PASSWORD='${DB_PASSWORD}'

OPEN_WEATHER_API_KEY=your_open_weather_api_key_here
CROSSREF_API_KEY=your_crossref_api_key_here
CROSSREF_API_EMAIL=your_email_here
GOOGLE_API_KEY=your_google_api_key_here

DJANGO_SUPERUSER_FIRST_NAME='Admin'
DJANGO_SUPERUSER_LAST_NAME='User'
DJANGO_SUPERUSER_USERNAME='admin'
DJANGO_SUPERUSER_EMAIL='admin@bespoke.com'
DJANGO_SUPERUSER_PASSWORD='usoadmin'

EMAIL_PASSWORD=your_email_password_here
EOF
chmod 600 "$USONLINE_DIR/local/.env"
echo "Local Development directory is ready! ensure you have completed the following steps:"
echo " 1. Update secrets in $USONLINE_DIR/local/.env "
echo " 2. Update '$USONLINE_DIR/local/settings.py' to override settings, and"
echo " 3. Check and update '$USONLINE_DIR/local/docker-compose.yml' as needed."