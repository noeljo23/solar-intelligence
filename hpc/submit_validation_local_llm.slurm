#!/bin/bash
#SBATCH --job-name=solar_intel_local_validate
#SBATCH --partition=gpu
#SBATCH --constraint=h200
#SBATCH --gres=gpu:h200:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=120G
#SBATCH --time=07:45:00
#SBATCH --output=logs/validate_%j.out
#SBATCH --error=logs/validate_%j.err

# Offline validation using a LOCAL LLM on H200 (no external API calls).
# Uses vLLM with Llama 3.3 70B Instruct to re-validate candidate facts.
# This is the belt-and-suspenders check: after Groq validator, we re-run
# validation locally so no data enters the KB without independent confirmation
# from a second model family.

set -euo pipefail

echo "===== Job start: $(date) ====="
nvidia-smi -L

module load python/3.13.5 || true

VENV="$HOME/.venv/solar-intel-vllm"
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
    # shellcheck disable=SC1090
    source "$VENV/bin/activate"
    pip install --quiet --upgrade pip
    pip install --quiet vllm transformers accelerate
else
    # shellcheck disable=SC1090
    source "$VENV/bin/activate"
fi

PROJECT_DIR="$HOME/solar-intelligence"
cd "$PROJECT_DIR"

CANDIDATES_FILE="${1:-data/collected/latest/candidates.jsonl}"
OUTPUT_FILE="${2:-data/validated/validated_$SLURM_JOB_ID.jsonl}"
MODEL="${3:-meta-llama/Llama-3.3-70B-Instruct}"

mkdir -p "$(dirname "$OUTPUT_FILE")" logs

# Start vLLM server in background
python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --dtype bfloat16 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.90 \
    --port 8000 &
VLLM_PID=$!

# Wait for server
for i in {1..60}; do
    if curl -s http://127.0.0.1:8000/health >/dev/null; then break; fi
    sleep 5
done

python -m hpc.local_validator \
    --candidates "$CANDIDATES_FILE" \
    --output "$OUTPUT_FILE" \
    --endpoint http://127.0.0.1:8000/v1

kill "$VLLM_PID" || true
echo "===== Job complete: $(date) ====="
