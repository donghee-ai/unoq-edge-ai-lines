#!/usr/bin/env bash
# run-kws.sh — one-shot build + enter unoq-kws container.
# Usage:
#   bash docker/run-kws.sh            # build (if missing) + enter
#   bash docker/run-kws.sh --rebuild  # force rebuild + enter
#
# Pattern: pose/vision/asr run scripts 와 동일 (SCRIPT_DIR + non-root user + --hostname).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="unoq-kws"
IMAGE_TAG="22.04"
IMAGE_FULL="${IMAGE_NAME}:${IMAGE_TAG}"
CONTAINER_NAME="unoq-kws"

REBUILD="${1:-}"

build_image() {
    local extra_args=("$@")
    docker build \
        "${extra_args[@]}" \
        --build-arg USER_UID="$(id -u)" \
        --build-arg USER_GID="$(id -g)" \
        -f "${SCRIPT_DIR}/Dockerfile.kws" \
        -t "${IMAGE_FULL}" \
        "${SCRIPT_DIR}"
}

if [ "${REBUILD}" == "--rebuild" ]; then
    echo "==> Force rebuild ${IMAGE_FULL}"
    build_image --no-cache
elif ! docker image inspect "${IMAGE_FULL}" >/dev/null 2>&1; then
    echo "==> First build ${IMAGE_FULL} (≈3 min — audio deps)"
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
