#!/bin/bash

SERVER=${1:-apache}
IMG_TAG="$(git describe)-$SERVER"
DOCKERFILE="./deploy/${SERVER}/Dockerfile"

# Build a docker image
# Check if buildah exists, then build the image

echo "Building the Docker/Podman image..."
if command -v buildah &> /dev/null; then
  buildah bud -t usonline:"${IMG_TAG}" -t usonline:${SERVER} -t usonline:latest -f ${DOCKERFILE} .
  buildah rmi --prune
elif command -v podman &> /dev/null; then
  podman build -t usonline:"${IMG_TAG}" -t usonline:${SERVER} -t usonline:latest -f ${DOCKERFILE} .
  podman image prune -f
elif command -v docker &> /dev/null; then
  docker build -t usonline:"${IMG_TAG}" -t usonline:${SERVER} -t usonline:latest -f ${DOCKERFILE} .
  docker image prune -f
else
  echo "Neither podman, buildah nor docker are installed. Exiting!"
  exit 1
fi