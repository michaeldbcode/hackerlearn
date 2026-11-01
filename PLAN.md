# served — plan & status

> **Resuming agent: read this whole file first.** It is the single source of truth.
> Update the **Status** and **Next steps** sections before every commit.

## Objective

Build "HackerTube, but for text": mine the full Hacker News archive for the most
**useful, informational** text content (explanations, essays, blog posts, papers,
tutorials, docs, visual/interactive explainers, books) and the best explanatory
comments, and serve it as a clean, text-first website.

Same method as Karpathy's HackerTube (<https://karpathy.bearblog.dev/hacker-tube/>):
he downloaded all HN comments from <https://huggingface.co/datasets/open-index/hacker-news>,
filtered them, ran Sonnet over them in a Claude Code workflow to remove spam, and
narrowed things down to ~40K comments recommending ~6.4K YouTube videos across ~150
topics, then wrapped that in a YouTube-like UI. We do the same, but for **text,
not video**.

**Out of scope for now:** personalisation from the owner's browser history (Chrome /
Safari). Planned for later (milestone 9).

Owner preferences:
- Work continuously. Hand bulk LLM work to cheaper **Haiku/Sonnet subagents**.
- Skip tests. Commit and push often with `git commit --no-verify` / `git push --no-verify`.
- A scheduled task resumes this work after each 5-hour usage reset (~02:30 owner time).
  Every session must leave the repo resumable.

---

## Core idea

Quality comes from **people vouching for something**, not from an LLM guessing.
A link counts when several *different* HN users recommend it in comments
("best explanation of X I've read"). The LLM only finds and cleans those
recommendations.

Tracks:
1. **Recommended links**: the evergreen library (main product).
2. **Great comments**: long, expert explanatory comments.
3. **Notable stories**: high score plus heavy discussion, informational only (no news churn).

---

## Dataset facts (verified 2026-11-01)

- `open-index/hacker-news`, public, **not gated**, ODC-BY licence, live-updated.
- Files: `data/YYYY/YYYY-MM.parquet` (monthly, 2006-10 → now), plus `today/**`.
- Download URL pattern:
  `https://huggingface.co/datasets/open-index/hacker-news/resolve/main/data/YYYY/YYYY-MM.parquet`
- Size: ~530 MB for 2024. Whole archive estimated at **~6–10 GB**. Disk here has ~30 GB free.
- Columns: `id, deleted, type(TINYINT), by, time(TIMESTAMPTZ), text(HTML), dead, parent,
  poll, kids(UINT[]), url, score, title, parts, descendants, words(VARCHAR[])`.
- `type` codes (from 2015-06 sample): **1 = story** (28K/month, has score),
  **2 = comment** (143K/month), 3/4/5 = job/poll/pollopt (rare; to confirm).
- **Comment `score` is always 0.** HN doesn't publish comment points, so comment
  quality must come from proxies (number of replies via `kids`, length, links to it,
  LLM judgement).
- No author karma column. Could fetch from the HN API `/v0/user/<id>.json` for the
  recommenders that matter.
- In DuckDB, quote the column `"by"` (it's a keyword).
- The HN API (`hacker-news.firebaseio.com/v0`) is reachable for live updates.

## Environment facts

- Cloud container: 4 CPUs, 15 GB RAM, ~30 GB disk. **It's temporary.** Anything not
  pushed to git is lost. `data/` (raw parquet, derived DBs) is gitignored and gets
  re-downloaded or rebuilt each session. **LLM outputs are small and MUST be committed**
  (under `work/`) so they're never paid for twice.
- Network: open web allowed (huggingface.co, HN API and arbitrary sites verified).
- No HF token needed (public dataset). Optional `HF_TOKEN` env var only raises rate limits.
- No `ANTHROPIC_API_KEY`. LLM work runs through **Claude Code subagents**
  (Agent tool with `model: "haiku"` or `"sonnet"`), the same "workflow" approach Karpathy used.
- Python 3.13. `pip install duckdb pyarrow` (add `trafilatura`, `httpx` later).

---

## Pipeline

### Stage 0: Download  (`served/download.py`)
Fetch all monthly parquet files into `data/raw/YYYY/`. Skip existing files, retry on failure.

### Stage 1: Extract and pre-filter (DuckDB, no LLM)
- From comments (`type=2`, not dead or deleted), extract URLs from `href="..."` in `text`
  (HTML-escaped: `&#x2F;` → `/`, `&amp;` → `&`).
- Normalise: lowercase host, strip `www.`/`m.`, force https, drop tracking params
  (`utm_*`, `ref`, `fbclid`…), drop trailing `/` and `#fragment`, unwrap
  `web.archive.org/web/*/` links.
- Drop: HN-internal links (save `news.ycombinator.com/item?id=` separately as
  comment-citation signal for Track 2), video (YouTube/Vimeo), social media
  (twitter/x, facebook, reddit*, linkedin), shorteners, Amazon/app stores (books handled
  later), Wikipedia (tag as reference and keep separately), images, and generic homepages
  (path `/` only).
- Output `data/derived/mentions.parquet`: `comment_id, story_id(parent), by, time,
  url_norm, domain, context (comment text, stripped, ≤1500 chars), n_kids`.
- Aggregate per `url_norm`: `n_distinct_users, n_mentions, first_year, last_year`.
- **Candidate rule: ≥ 3 distinct users mention the link** (tune after seeing the
  distribution). Also run a phrase heuristic ("best explanation", "highly recommend",
  "great intro", "must read", "worth reading", "I learned", "excellent", "classic",
  "check out"…) to rank mentions.
- Target: the LLM sees **~50–150K mentions** (Karpathy's final set was 40K). If there
  are more, raise the threshold or sample the top N mentions per URL (max 5).

### Stage 2: LLM classification of mentions (subagents)
- Write batches of ~150 mentions to `work/batches/NNNNN.jsonl` (id, url, context).
  Inputs are reproducible from the data, but commit them anyway (they're small) so a
  resumed session can classify immediately.
- Each **Haiku** subagent reads one batch file and writes `work/labels/NNNNN.jsonl`,
  one JSON per line:
  `{"comment_id", "url", "label": "recommend|cite|self_promo|spam|negative|other",
    "reason": "≤20 words, why they recommend it", "kind": "explainer|essay|tutorial|
    paper|docs|book|visual|reference|tool|news|other", "depth": "intro|intermediate|expert"}`
- **Resumable:** a batch is done once its labels file exists and has the right line
  count. Next session = list batches without labels and continue.
- Run several subagents in parallel (~4–6). Commit and push after every few batches.
- Sonnet spot-check: on ~2% of batches, a Sonnet subagent re-labels them. Log
  agreement in `work/qa.md`.

### Stage 3: Aggregate per link
score = distinct users with label `recommend` (main signal), plus a bonus for years
spanned (evergreen), the story score if the link was also submitted, and a penalty for
self-promotion or one-account campaigns. Keep links with ≥ 2 genuine recommenders.
Output `work/links.jsonl` (committed).

### Stage 4: Fetch and enrich survivors
- `httpx` + `trafilatura`: title, author, date, main text, word count, image count.
  Polite: robots.txt, ≤ 2 requests/sec per domain, real User-Agent. If the link is dead,
  try the Wayback Machine `https://archive.org/wait/...` or `http://archive.org/wayback/available?url=`.
- Store page text in `data/pages/` (gitignored). Store metadata in `work/pages.jsonl` (committed).
- Haiku subagent pass: 3 bullets of "what you'll learn", confirm kind and depth, and
  flag whether it's time-sensitive.
- Taxonomy: cluster titles and reasons, then have a Sonnet subagent name and merge
  them into ~150 topics → `work/topics.json`. Haiku then assigns each link a topic.

### Stage 5: Great comments
Pre-filter: comments over 150 words with ≥ 2 kids, not dead; boost ones that other
comments link to (`item?id=`). Haiku judge: "substantive explanation a curious
reader would learn from?" → score, topic and a one-line summary. → `work/comments.jsonl`.

### Stage 6: Notable stories
Stories with score ≥ ~300 and descendants ≥ ~100, filtered by Haiku to informational
content. Daily refresh from the HN API later.

### Stage 7: Site
Static site built from `work/*.jsonl` (Python generator → `site/`, plain HTML/CSS/JS,
no framework). Views:
- **Best of all time**
- **Topics**
- **Great comments**
- **Notable stories**
- **Search** (client-side)

Each card shows title, domain, year, kind, depth, takeaway bullets, "recommended by N
on HN", the best quoted reason, and links to the threads. Local browser state for
read / saved / hidden. Keyboard shortcuts. A downloadable data export.

### Stage 8: Daily updates and deploy
A cron job pulls new items from the HN API (or the dataset's `today/` split), mines new
recommendations incrementally, and rebuilds the site. Deploy to a VPS or static host
plus a domain; the owner provides these.

---

## Repo layout

```
PLAN.md            ← this file (status + next steps)
CLAUDE.md          ← short pointer for agents
served/            ← python package: download.py, extract.py, batches.py, aggregate.py, fetch.py, build_site.py
work/              ← COMMITTED small outputs: batches/, labels/, links.jsonl, pages.jsonl, topics.json, qa.md, stats.md
data/              ← gitignored: raw/ (parquet), derived/, pages/
site/              ← generated static site
```

---

## Status

**Session 1 (2026-11-01)**
- [x] Repo connected, plan written.
- [x] Network verified: HF, HN API and arbitrary sites are reachable.
- [x] Dataset schema inspected on the 2015-06 sample (see Dataset facts).
- [x] `.gitignore`, `CLAUDE.md`, `served/download.py` (Stage 0 downloader) written.
- [ ] Stage 0 full download: not started.
- [ ] Stages 1–8: not started.

## Next steps (exact)

1. `pip install duckdb pyarrow httpx trafilatura`
2. `python -m served.download` (run in the background; ~6–10 GB).
3. Confirm the type codes 3/4/5, then write `served/extract.py` (Stage 1). Write
   `work/stats.md` with: total comments, comments with links, distinct URLs, the
   distribution of distinct-user counts, top 50 domains, and the candidate count at
   thresholds 2/3/5.
4. Choose a threshold so candidate mentions land at ~50–150K. Write the batches
   (`served/batches.py`). Commit.
5. Pilot: 3 Haiku subagents on 3 batches, plus 1 Sonnet check. Review the labels and
   adjust the prompt (save it in `work/prompt_classify.md`). Commit.
6. Full Stage 2 with parallel Haiku subagents. Commit and push every ~10 batches.
   Update Status here.
7. Then Stages 3 → 7 in order.

## Open questions for the owner
- Include books (Amazon/Goodreads) and Wikipedia as their own sections?
- Hosting: a VPS like HackerTube, or a static host? Domain name?
