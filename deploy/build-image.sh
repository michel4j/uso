#!/bin/bash

# Build a docker image
# Check if buildah exists, then build the image
echo "Building the Docker/Podman image..."
if command -v buildah &> /dev/null; then
  buildah bud -t usonline:$(git describe) -t usonline:latest .
  buildah rmi --prune
elif command -v podman &> /dev/null; then
  podman build -t usonline:$(git describe) -t usonline:latest .
  podman image prune -f
elif command -v docker &> /dev/null; then
  docker build -t usonline:$(git describe) -t usonline:latest .
  docker image prune -f
else
  echo "Neither buildah nor docker is installed. Exiting."
  exit 1
fi