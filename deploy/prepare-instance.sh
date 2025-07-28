#!/bin/bash

set -e

if [ -z "$1" ]; then
  echo "Usage: $0 <directory>"
  echo "Please provide a parent directory for the instance."
  echo "A new directory named 'usonline' will be created within it."
  exit 1
fi

SCRIPT_NAME="$0"
PARENT_DIR="$1"
USONLINE_DIR="$PARENT_DIR/usonline"
SCRIPT_DIR="$(dirname $SCRIPT_NAME)"

. "$SCRIPT_DIR/build-image.sh" && echo "Image built successfully."


if [ -d "$USONLINE_DIR" ]; then
  echo "The directory '$USONLINE_DIR' already exists. Exiting."
  exit 1
else
  mkdir -p "$USONLINE_DIR"
  echo "Created directory '$USONLINE_DIR'."
fi

# Create directory structure
mkdir -p "$USONLINE_DIR/local/kickstart" &&
mkdir -p "$USONLINE_DIR/local/media/css" &&
mkdir -p "$USONLINE_DIR/local/logs" &&
mkdir -p "$USONLINE_DIR/database"

# Copy configuration files
DB_PASSWORD=$(openssl rand -base64 32 | tr -d '\n="`')
SECRET_KEY=$(openssl rand -base64 64 | tr -d '\n="`')
cp "${SCRIPT_DIR}/settings_template.py" "$USONLINE_DIR/local/settings.py" &&
cp "${SCRIPT_DIR}/custom.css" "$USONLINE_DIR/local/media/css/" &&
cp "${SCRIPT_DIR}/docker-compose.yml" "$USONLINE_DIR/" &&

cat <<EOF > "$USONLINE_DIR/.env"
SECRET_KEY='${SECRET_KEY}'

DB_PASSWORD='${DB_PASSWORD}'

OPENAI_API_KEY=your_openai_api_key_here
GOOGLE_API_KEY=your_google_api_key_here

ADMIN_FIRST_NAME='Admin'
ADMIN_LAST_NAME='User'
ADMIN_USERNAME='admin'
ADMIN_EMAIL='admin@bespoke.com'
ADMIN_PASSWORD='usoadmin'

EMAIL_PASSWORD=your_email_password_here
EOF
chmod 600 "$USONLINE_DIR/.env"
echo "Instance directory is ready! Before starting the instance, ensure you have completed the following steps:"
echo " 1. Update secrets in local/.env "
echo " 2. Update 'local/settings.py' to override settings, and"
echo " 3. Check and update 'docker-compose.yml' as needed."