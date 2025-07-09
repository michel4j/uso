#!/bin/bash

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

# Build a docker image
# Check if buildah exists, then build the image
echo "Building the Docker/Podman image..."
if command -v buildah &> /dev/null; then
  buildah bud -t usonline:$(git describe) -t usonline:latest .
elif command -v docker &> /dev/null; then
  docker build -t usonline:$(git describe) -t usonline:latest .
  docker image prune -f
else
  echo "Neither buildah nor docker is installed. Exiting."
  exit 1
fi


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
cp "${SCRIPT_DIR}/settings_template.py" "$USONLINE_DIR/local/settings.py" &&
cp "${SCRIPT_DIR}/custom.css" "$USONLINE_DIR/local/media/css/" &&
cp "${SCRIPT_DIR}/docker-compose.yml" "$USONLINE_DIR/" &&
echo "Instance directory is ready. Please update 'local/settings.py' and "
echo "'docker-compose.yml' as needed before starting the instance."