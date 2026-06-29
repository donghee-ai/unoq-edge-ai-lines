#!/usr/bin/env bash
# run-asr.sh — one-shot build + enter asr-dev container.
# Usage:
#   bash docker/run-asr.sh                # build (if missing) + enter
#   bash docker/run-asr.sh --rebuild      # force rebuild + enter
#
# Mount strategy: SCRIPT_DIR pattern so it works regardless of cwd.
# Project root is mounted at /work; build context is docker/ folder only.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="unoq-asr-dev"
IMAGE_TAG="22.04"
IMAGE_FULL="${IMAGE_NAME}:${IMAGE_TAG}"
CONTAINER_NAME="unoq-asr-dev"

REBUILD="${1:-}"

build_image() {
    local extra_args=("$@")
    docker build \
        "${extra_args[@]}" \
        --build-arg USER_UID="$(id -u)" \
        --build-arg USER_GID="$(id -g)" \
        -f "${SCRIPT_DIR}/Dockerfile.asr" \
        -t "${IMAGE_FULL}" \
        "${SCRIPT_DIR}"
}

if [ "${REBUILD}" == "--rebuild" ]; then
    echo "==> Force rebuild ${IMAGE_FULL}"
    build_image --no-cache
elif ! docker image inspect "${IMAGE_FULL}" >/dev/null 2>&1; then
    echo "==> First build ${IMAGE_FULL} (≈10 min)"
    build_image
else
    echo "==> Reusing cached image ${IMAGE_FULL}"
fi

echo "==> Enter container ${CONTAINER_NAME} (mount: ${PROJECT_ROOT} -> /work)"
docker run --rm -it \
    --name "${CONTAINER_NAME}" \
    --hostname "${CONTAINER_NAME}" \
    -v "${PROJECT_ROOT}:/work" \
    -w /work \
    "${IMAGE_FULL}" \
    bash
