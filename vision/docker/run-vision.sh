#!/usr/bin/env bash
# run-vision.sh — one-shot build + enter unoq-yolo-dev container.
# Usage:
#   bash docker/run-vision.sh             # build (if missing) + enter
#   bash docker/run-vision.sh --rebuild   # force rebuild + enter
#
# Mount strategy: SCRIPT_DIR pattern so it works regardless of cwd.
# Project root (vision/) is mounted at /work; build context is docker/ folder only.
# (asr/pose 라인과 동일 패턴 — 2026-06-29 monorepo 통합)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="unoq-yolo-dev"
IMAGE_TAG="22.04"
IMAGE_FULL="${IMAGE_NAME}:${IMAGE_TAG}"
CONTAINER_NAME="unoq-yolo-dev"

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

build_image() {
    local extra_args=("$@")
    docker build \
        "${extra_args[@]}" \
        --build-arg USER_UID="${USER_UID}" \
        --build-arg USER_GID="${USER_GID}" \
        -f "${SCRIPT_DIR}/Dockerfile.vision" \
        -t "${IMAGE_FULL}" \
        "${SCRIPT_DIR}"
}

if [[ "${REBUILD}" -eq 1 ]]; then
    echo "==> Force rebuild ${IMAGE_FULL}"
    build_image --no-cache
elif ! docker image inspect "${IMAGE_FULL}" >/dev/null 2>&1; then
    echo "==> First build ${IMAGE_FULL}"
    build_image
else
    echo "==> Reusing existing image ${IMAGE_FULL} (use --rebuild to force rebuild)"
fi

echo "==> Starting container (mount: ${PROJECT_ROOT} -> /work)"
docker run --rm -it \
    --name "${CONTAINER_NAME}" \
    --hostname "${CONTAINER_NAME}" \
    -v "${PROJECT_ROOT}:/work" \
    -w /work \
    "${IMAGE_FULL}" \
    "${@:-/bin/bash}"
