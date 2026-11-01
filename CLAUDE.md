# served

Read `PLAN.md` first: it has the objective, dataset facts, pipeline, **Status** and **exact Next steps**.

Rules:
- Raw/derived data lives in `data/` (gitignored, rebuild each session). Small LLM outputs go in `work/` and MUST be committed.
- Bulk LLM work runs through Claude Code subagents (`model: "haiku"`, Sonnet for spot-checks). No API key needed.
- Skip tests. Commit and push often: `git commit --no-verify`, `git push --no-verify -u origin main`.
- Update PLAN.md Status / Next steps before every commit so the next session can resume.
