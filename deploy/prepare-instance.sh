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
PASSWORD=$(openssl rand -base64 32 | tr -d '\n=')
SECRET_KEY=$(openssl rand -base64 64 | tr -d '\n=')
cp "${SCRIPT_DIR}/settings_template.py" "$USONLINE_DIR/local/settings.py" &&
cp "${SCRIPT_DIR}/custom.css" "$USONLINE_DIR/local/media/css/" &&
cp "${SCRIPT_DIR}/docker-compose.yml" "$USONLINE_DIR/" &&
sed -i "s|POSTGRES_PASSWORD\:.*$|POSTGRES_PASSWORD: ${PASSWORD}|g" $USONLINE_DIR/docker-compose.yml
sed -i "s|'PASSWORD':.*$|'PASSWORD': '${PASSWORD}',|g" $USONLINE_DIR/local/settings.py
sed -i "s|SECRET_KEY = .*$|SECRET_KEY = '${SECRET_KEY}'|g" $USONLINE_DIR/local/settings.py
echo "Instance directory is ready. Please update 'local/settings.py' and "
echo "'docker-compose.yml' as needed before starting the instance."