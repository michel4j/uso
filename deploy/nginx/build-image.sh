#!/bin/bash

set -e

# Build a docker image
# Check if buildah exists, then build the image
echo "Building the Docker/Podman image..."
if command -v buildah &> /dev/null; then
  buildah bud -t usonline:$(git describe)-nginx -t usonline:latest -f ./deploy/nginx/Dockerfile .
  buildah rmi --prune
elif command -v podman &> /dev/null; then
  podman build -t usonline:$(git describe)-nginx -t usonline:latest -f ./deploy/nginx/Dockerfile .
  podman image prune -f
elif command -v docker &> /dev/null; then
  docker build -t usonline:$(git describe)-nginx -t usonline:latest -f ./deploy/nginx/Dockerfile .
  docker image prune -f
else
  echo "Neither podman, buildah nor docker are installed. Exiting!"
  exit 1
fi