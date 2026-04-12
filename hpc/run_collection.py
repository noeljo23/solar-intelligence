"""
HPC entry point for running the collection pipeline.

Reads a JSONL batch file where each line is:
  {"country": "Mexico", "state": "Sonora", "dimension": "cost_economics",
   "sources": [{"url": "...", "organization": "CRE", "document": "..."}]}

Runs CollectorAgent + ValidatorAgent for each, writes outputs to JSONL.
Designed to run under SLURM on Explorer H200 node (see submit_collection.slurm).
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Allow `python -m hpc.run_collection` from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_collector import run_pipeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="HPC solar intel collection pipeline")
    p.add_argument("--batch", type=Path, required=True, help="JSONL batch file")
    p.add_argument("--output-dir", type=Path, required=True, help="Output directory")
    p.add_argument("--max-workers", type=int, default=4, help="Parallel jobs")
    return p.parse_args()


def process_job(job: dict, out_dir: Path) -> tuple[str, int, int]:
    """Run pipeline for a single (country, state, dimension) job."""
    country = job["country"]
    state = job.get("state")
    dimension = job["dimension"]
    job_key = f"{country}_{(state or 'NATIONAL').replace(' ', '_')}_{dimension}"
    out_path = out_dir / f"{job_key}.jsonl"

    result = run_pipeline(
        country=country,
        state=state,
        dimension=dimension,
        sources=job["sources"],
        output_path=out_path,
    )
    return job_key, len(result.accepted), len(result.rejected)


def main() -> int:
    args = parse_args()
    if not args.batch.exists():
        print(f"ERROR: batch file not found: {args.batch}")
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    jobs: list[dict] = []
    with open(args.batch, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                jobs.append(json.loads(line))

    print(f"Loaded {len(jobs)} jobs. Running with {args.max_workers} workers.")
    total_accepted = 0
    total_rejected = 0

    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futures = [pool.submit(process_job, j, args.output_dir) for j in jobs]
        for fut in as_completed(futures):
            try:
                key, acc, rej = fut.result()
                print(f"  {key}: accepted={acc}, rejected={rej}")
                total_accepted += acc
                total_rejected += rej
            except Exception as e:  # noqa: BLE001 — report and continue
                print(f"  job failed: {e}")

    print(f"\nTotal accepted: {total_accepted}")
    print(f"Total rejected: {total_rejected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
