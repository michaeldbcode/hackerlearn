#!/bin/bash
# usage: scripts/label_one.sh <batches|cbatches> NNNNN [model]
kind=$1; n=$2; model=${3:-haiku}
case $kind in batches) prompt=work/prompt_classify.md; out=work/labels;; cbatches) prompt=work/prompt_comments.md; out=work/clabels;; sbatches) prompt=work/prompt_stories.md; out=work/slabels;; esac
mkdir -p $out logs
lines=$(wc -l < work/$kind/$n.jsonl)
timeout 900 claude -p --model "$model" --allowedTools=Read,Write \
  "Working dir $(pwd). Read the instructions in $prompt and follow them exactly for batch $n: read work/$kind/$n.jsonl (all $lines lines; use offset/limit to read the whole file) and write $out/$n.jsonl with exactly one JSON line per input line ($lines lines). Do not write any other files. Reply 'done'." \
  > logs/$kind-$n.log 2>&1
echo "$kind $n exit=$? lines=$(wc -l < $out/$n.jsonl 2>/dev/null)"
