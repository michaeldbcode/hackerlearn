#!/bin/bash
# Process all pending batches with P parallel headless Claude workers. Safe to re-run (resumable).
# usage: scripts/run_labels.sh <batches|cbatches> [P] [model]
cd "$(dirname "$0")/.."
kind=${1:-batches}; P=${2:-8}; model=${3:-haiku}
for pass in 1 2 3; do
  todo=$(python3 -m served.pending $kind | cut -d: -f2)
  [ -z "${todo// }" ] && break
  echo $todo | tr ' ' '\n' | xargs -P $P -I{} scripts/label_one.sh $kind {} $model
done
python3 -m served.pending $kind | cut -c1-80
