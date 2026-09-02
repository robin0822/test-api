#!/usr/bin/env bash
set -Eeuo pipefail

IMAGE="${IMAGE:-ghcr.io/robin0822/test-api}"
TAG="${TAG:-$(git rev-parse --short HEAD)}"
PLATFORMS="${PLATFORMS:-linux/arm64}"
PUSH="${PUSH:-false}"

command -v docker >/dev/null || { echo 'Docker is required' >&2; exit 1; }
output=(--load)
if [[ "${PUSH}" == "true" ]]; then
  output=(--push)
fi

docker buildx build \
  --platform "${PLATFORMS}" \
  --tag "${IMAGE}:${TAG}" \
  --tag "${IMAGE}:latest" \
  "${output[@]}" \
  .
