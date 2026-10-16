#!/usr/bin/env bash
# Start the same embedding service on a compatible local GPU or Kaggle GPU.
# Install vLLM in a separate serving environment before running this script.
# This script only starts the service; it does not build the Chroma index.
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python}"
MODEL="${MODEL:-Qwen/Qwen3-Embedding-0.6B}"
MODEL_REVISION="${MODEL_REVISION:-97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3}"
TOKENIZER_REVISION="${TOKENIZER_REVISION:-$MODEL_REVISION}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-$MODEL}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-2048}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.5}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

# Apply only an explicitly supplied library path, in this process and children.
# Kaggle may need its environment's nvjitlink/lib plus /usr/local/nvidia/lib64.
# Leave LD_LIBRARY_PATH untouched on machines that do not need this override.
if [[ -n "${VLLM_LIBRARY_PATH:-}" ]]; then
    export LD_LIBRARY_PATH="$VLLM_LIBRARY_PATH"
fi
# This is our launcher setting, not a vLLM environment variable.
unset VLLM_LIBRARY_PATH

if [[ ! "$MODEL_REVISION" =~ ^[0-9a-fA-F]{40}$ ]] || \
   [[ ! "$TOKENIZER_REVISION" =~ ^[0-9a-fA-F]{40}$ ]]; then
    printf 'MODEL_REVISION and TOKENIZER_REVISION must be full 40-character commit SHAs.\n' >&2
    exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    printf 'Python executable not found: %s\nSet PYTHON_BIN to your serving environment Python.\n' "$PYTHON_BIN" >&2
    exit 1
fi

# Check metadata without loading model weights or initializing CUDA.
"$PYTHON_BIN" -c '
from importlib.metadata import PackageNotFoundError, version
import sys
try:
    installed = version("vllm")
except PackageNotFoundError:
    sys.exit("vLLM is not installed in this Python environment.")
if installed != "0.18.0":
    sys.exit(f"Expected vLLM 0.18.0, found {installed}. Use the verified serving environment.")
print(f"Serving environment: vLLM {installed}", flush=True)
'

printf 'Starting embedding server: model=%s GPU=%s host=%s port=%s\n' \
    "$MODEL" "$CUDA_VISIBLE_DEVICES" "$HOST" "$PORT"
printf 'Pinned model revision: %s; tokenizer revision: %s\n' \
    "$MODEL_REVISION" "$TOKENIZER_REVISION"

# exec forwards signals directly to the server; logs stay in the terminal.
# Use this Python's CLI rather than a potentially unrelated vllm on PATH.
exec "$PYTHON_BIN" -m vllm.entrypoints.cli.main serve "$MODEL" \
    --revision "$MODEL_REVISION" \
    --tokenizer-revision "$TOKENIZER_REVISION" \
    --served-model-name "$SERVED_MODEL_NAME" \
    --runner pooling \
    --convert embed \
    --dtype float16 \
    --tensor-parallel-size 1 \
    --host "$HOST" \
    --port "$PORT" \
    --max-model-len "$MAX_MODEL_LEN" \
    --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
    --max-num-seqs 16 \
    --enforce-eager
