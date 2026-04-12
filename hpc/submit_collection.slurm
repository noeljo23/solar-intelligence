#!/bin/bash
#SBATCH --job-name=solar_intel_collect
#SBATCH --partition=gpu
#SBATCH --gres=gpu:h200:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=07:30:00
#SBATCH --output=logs/collect_%j.out
#SBATCH --error=logs/collect_%j.err

# H200 selection: relies on --gres=gpu:h200:1. No explicit --constraint needed
# on Explorer; h200 GPU type is matched via GRES, and the h200 nodes
# (d4052-d4055) carry AVAIL_FEATURES 'cascadelake,pro' rather than an 'h200' tag.

# PowerTrust Solar Intelligence — HPC Data Collection Pipeline
# Runs collector + validator agents across a batch of (country, state, dimension)
# tuples on a single H200 node. 8hr soft limit (partition max).

set -euo pipefail

echo "===== Job start: $(date) ====="
echo "Node: $(hostname)"
echo "GPUs:"
nvidia-smi -L

# --- Environment setup ---
module load python/3.13.5 || true

VENV="$HOME/.venv/solar-intel"
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi
# shellcheck disable=SC1090
source "$VENV/bin/activate"

PROJECT_DIR="$HOME/solar-intelligence"
cd "$PROJECT_DIR"
pip install --quiet -r requirements.txt
pip install --quiet httpx beautifulsoup4 lxml tenacity

# --- Secrets: expect GROQ_API_KEY in environment (set via OOD or .env.hpc) ---
if [ -z "${GROQ_API_KEY:-}" ] && [ -f ".env.hpc" ]; then
    set -a
    # shellcheck disable=SC1091
    source .env.hpc
    set +a
fi
if [ -z "${GROQ_API_KEY:-}" ]; then
    echo "ERROR: GROQ_API_KEY not set. Abort."
    exit 1
fi

# --- Run pipeline ---
BATCH_FILE="${1:-hpc/batches/default_batch.jsonl}"
OUTPUT_DIR="${2:-data/collected/$SLURM_JOB_ID}"
mkdir -p "$OUTPUT_DIR" logs

echo "Batch file: $BATCH_FILE"
echo "Output dir: $OUTPUT_DIR"

python -m hpc.run_collection \
    --batch "$BATCH_FILE" \
    --output-dir "$OUTPUT_DIR" \
    --max-workers 4

echo "===== Job complete: $(date) ====="
