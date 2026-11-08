#!/usr/bin/env bash
# Quickstart script to download a recommended open-weights GGUF model and run llama-server

set -euo pipefail

MODEL_DIR="${HOME}/models"
mkdir -p "${MODEL_DIR}"

echo "======================================================================"
echo " 🇺🇸 Presidential AI Platform - GGUF Inference Server Setup"
echo "======================================================================"

# Recommended high-efficiency quantized model:
# Llama-3.1-8B-Instruct-Q4_K_M (Fast, high throughput, ~4.9GB VRAM/RAM)
# For enterprise presidential scale: Llama-3.1-70B-Instruct-Q4_K_M (~43GB VRAM)
MODEL_NAME="Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
MODEL_URL="https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"

if [ ! -f "${MODEL_DIR}/${MODEL_NAME}" ]; then
    echo "Downloading ${MODEL_NAME} to ${MODEL_DIR}..."
    echo "Note: If you have already downloaded a GGUF model, place it in ${MODEL_DIR}."
    # curl -L "${MODEL_URL}" -o "${MODEL_DIR}/${MODEL_NAME}"
    echo "To download manually: curl -L '${MODEL_URL}' -o '${MODEL_DIR}/${MODEL_NAME}'"
else
    echo "Found existing model at ${MODEL_DIR}/${MODEL_NAME}"
fi

echo ""
echo "To serve the GGUF model with multi-slot continuous batching for high citizen concurrency:"
echo ""
echo "  llama-server \\"
echo "    --model ${MODEL_DIR}/${MODEL_NAME} \\"
echo "    --ctx-size 8192 \\"
echo "    --n-gpu-layers 33 \\"
echo "    --parallel 8 \\"
echo "    --port 8080 \\"
echo "    --host 127.0.0.1"
echo ""
echo "Once running, the Presidential AI Platform will automatically route inference to port 8080."
