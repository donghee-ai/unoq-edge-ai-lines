#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="unoq-yolo-dev"
IMAGE_TAG="22.04"
CONTAINER_NAME="unoq-yolo-dev"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REBUILD=0
if [[ "${1:-}" == "--rebuild" ]]; then
    REBUILD=1
    shift
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker is not installed or not on PATH." >&2
    exit 1
fi

USER_UID="$(id -u)"
USER_GID="$(id -g)"

needs_build=0
if [[ "${REBUILD}" -eq 1 ]]; then
    needs_build=1
elif ! docker image inspect "${IMAGE_NAME}:${IMAGE_TAG}" >/dev/null 2>&1; then
    needs_build=1
fi

if [[ "${needs_build}" -eq 1 ]]; then
    echo "==> Building ${IMAGE_NAME}:${IMAGE_TAG} (UID=${USER_UID} GID=${USER_GID})"
    docker build \
        --build-arg USER_UID="${USER_UID}" \
        --build-arg USER_GID="${USER_GID}" \
        -t "${IMAGE_NAME}:${IMAGE_TAG}" \
        "${PROJECT_ROOT}"
else
    echo "==> Reusing existing image ${IMAGE_NAME}:${IMAGE_TAG} (use --rebuild to force rebuild)"
fi

echo "==> Starting container (project mounted at /work)"
docker run --rm -it \
    --name "${CONTAINER_NAME}" \
    --hostname "${CONTAINER_NAME}" \
    -v "${PROJECT_ROOT}:/work" \
    -w /work \
    "${IMAGE_NAME}:${IMAGE_TAG}" \
    "${@:-/bin/bash}"
