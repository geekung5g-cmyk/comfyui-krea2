#!/usr/bin/env bash
# Build + push the template image.
#   DOCKER_USER=yourname ./build.sh              -> cu129 (default)
#   DOCKER_USER=yourname VARIANT=cu128 ./build.sh
set -Eeuo pipefail

DOCKER_USER="${DOCKER_USER:?set DOCKER_USER to your Docker Hub username}"
IMAGE="${IMAGE:-comfyui-krea2}"
VERSION="${VERSION:-1.0}"
VARIANT="${VARIANT:-cu129}"

case "${VARIANT}" in
  cu128) CUDA_IMAGE=nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04; TORCH=2.11.0 ;;
  cu129) CUDA_IMAGE=nvidia/cuda:12.9.1-cudnn-runtime-ubuntu24.04; TORCH=2.13.0 ;;
  cu130) CUDA_IMAGE=nvidia/cuda:13.0.1-cudnn-runtime-ubuntu24.04; TORCH=2.13.0 ;;
  *) echo "unknown VARIANT ${VARIANT} (cu128|cu129|cu130)"; exit 1 ;;
esac

TAG="${DOCKER_USER}/${IMAGE}:${VERSION}-${VARIANT}"
echo ">> building ${TAG}  (base ${CUDA_IMAGE}, torch ${TORCH}+${VARIANT})"

docker build \
  --build-arg "CUDA_IMAGE=${CUDA_IMAGE}" \
  --build-arg "TORCH_CHANNEL=${VARIANT}" \
  --build-arg "TORCH_VERSION=${TORCH}" \
  -t "${TAG}" .

if [[ "${PUSH:-1}" == "1" ]]; then
  docker push "${TAG}"
  echo ">> pushed ${TAG}"
fi
echo ">> use this in the Vast.ai template Image Path: ${TAG}"
