"""List batches without complete, valid labels. usage: python -m served.pending [batches|cbatches]"""
import json, os, sys
kind = sys.argv[1] if len(sys.argv) > 1 else "batches"
lab = {"batches": "labels", "cbatches": "clabels", "sbatches": "slabels"}[kind]
todo = []
for f in sorted(os.listdir(f"work/{kind}")):
    n = sum(1 for _ in open(f"work/{kind}/{f}"))
    p = f"work/{lab}/{f}"
    try:
        ok = sum(1 for l in open(p) if l.strip() and json.loads(l)) == n
    except Exception:
        ok = False
    if not ok: todo.append(f[:-6])
print(len(todo), "pending:", " ".join(todo))
