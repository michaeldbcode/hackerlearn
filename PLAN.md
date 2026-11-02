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
served/            ← python package: download, extract, batches, comments, stories, pending, fetch, build
work/              ← COMMITTED small outputs: batches/, labels/, links.jsonl, pages.jsonl, topics.json, qa.md, stats.md
data/              ← gitignored: raw/ (parquet), derived/, pages/
docs/              ← the static site (index.html + generated data/)
scripts/           ← run_labels.sh, label_one.sh, autocommit.sh
```

---

## Status

**Session 1 (2026-11-01, evening)**: pipeline built end to end. Bulk labelling is running.

Done:
- [x] Stage 0: full dataset downloaded (239 monthly files, 12.4 GB, ~4 min with HF_TOKEN). `python3 -m served.download 8`
- [x] Stage 1: `served/extract.py`. **4.68M link mentions, 2.87M distinct URLs, 260K users** (runs in ~1 min on 4 cores).
  Distinct-user thresholds: ≥2 → 444K URLs, ≥3 → 201K, ≥5 → 84K, ≥10 → 27K.
  Wikipedia (45K URLs ≥3), GitHub (19K) and Amazon (books) are excluded for now; they'd make good separate sections later.
- [x] **Decision: classify per URL, not per mention.** Each URL comes with up to 3 snippets from different commenters, preferring ones with recommendation words. That's ~10× cheaper.
  `served/batches.py 5` → **47,405 URLs (≥5 distinct users) in 238 batches** of 200 (`work/batches/`), sorted by user count descending, so the best come first.
- [x] Stage 2 prompt: `work/prompt_classify.md`. The pilot was high quality and strict (~40% kept).
- [x] Stage 5 prep: `served/comments.py` → 90K candidate comments (≥200 words and (≥4 replies or linked by ≥2 users)). The top 6,000 by heuristic are in `work/cbatches/` (60 × 100). Prompt: `work/prompt_comments.md`.
- [x] Stage 6 prep: `served/stories.py` → 32,042 stories (score ≥300, comments ≥100) in `work/sbatches/` (81 × 400). Prompt: `work/prompt_stories.md`.
- [x] Stage 4: `served/fetch.py`. Async httpx + trafilatura; title/author/date/words/excerpt for kept links → `work/pages.jsonl` (append-only, resumable). ~70% yield a readable excerpt.
- [x] Stages 3+7: `served/build.py` merges labels + pages → `docs/data/{links,comments,stories,topics}.json` + `docs/data/ex/*.json` (excerpts, lazy-loaded).
  Rank score = `2*q + log2(users+1)`, with comics −1.5.
- [x] Site: `docs/index.html`, a single static page with no build step. HN-dense list, Paul Graham-style serif text, dark mode.
  Tabs: reads / comments / threads / saved. Search, topic, kind and sort filters. Expand (shows a commenter quote + page excerpt), open, hn discussion (Algolia search), save, dismiss (stored in localStorage).
  Keys: j/k, e/Enter, o, x, s, /. Preview locally: `cd docs && python3 -m http.server`.
  Lives in `docs/` so GitHub Pages can serve it (Settings → Pages → main /docs). **The owner decides whether to make it public.**

How bulk labelling runs (no API key needed):
- `scripts/run_labels.sh <batches|cbatches|sbatches> <P> haiku` runs P parallel headless `claude -p --model haiku` workers, one batch each (`scripts/label_one.sh`). Logs go to `logs/`.
  Resumable: `python3 -m served.pending <kind>` lists batches without a complete labels file.
  Gotcha: use `--allowedTools=Read,Write` (with `=`). Without it, the flag swallows the prompt.
  Gotcha: never `pkill -f <pattern>` where the pattern also appears in your own command line; it kills your shell.
- Workers sleep 10 min and retry when the usage limit is hit (`touch data/STOP` makes them exit).
- Speed: ~7 min per batch per worker. Ran 10 workers on links + 4 on comments + 4 on stories.
- `scripts/autocommit.sh` loops: fetch new pages → build → commit + push (every ~10 min).

**Session 2 (2026-11-02)**
- The overnight usage limit killed the runners, and the 02:30 resume didn't fire (no commits between 09:01 and 17:46). Restarted manually.
- [x] Topic taxonomy: `work/topic_map.json` (42 canonical topics plus keyword fallback, made by Sonnet from `work/topics_raw.tsv`); applied in `served/build.py` `norm_topic`.
- [x] Coverage extended: `python3 -m served.batches 4 4 238` appended **126 batches (00238–00363)** for 25,158 URLs with exactly 4 distinct users (ids start at 47600).
  `served/batches.py` args: `MIN MAX START_BATCH`.
- **Repo renamed to `michaeldbcode/hackerlearn`.** The site is live on GitHub Pages: https://michaeldbcode.github.io/hackerlearn/ (served from `main` /docs). Push through the old URL `github.com/michaeldbcode/served` (it redirects); this session's git proxy only authorises that name.
- Fixed: `.gitignore` had `data/`, which also ignored `docs/data/`, so the Pages site was blank. It's now `/data/`.
- The overnight scheduled session committed to branch `claude/eager-ptolemy-83r8zr`; merged into main. **Resuming sessions: always work on and push to `main`** (Pages deploys from it).
- Comments track complete (60/60). Site preview artifact (private): https://claude.ai/artifact/P4PYcyzksxhb6KqswrcMWf. Republish `docs/index.html` with all `docs/data/**` files to update it.

## Next steps (exact): for a resuming session

1. Setup (fresh container): `pip install duckdb pyarrow httpx trafilatura`.
   Labels, batches and pages are in git, so **you don't need the raw data** unless re-running Stages 0/1/5/6 prep.
2. Check progress: `for k in batches cbatches sbatches; do python3 -m served.pending $k | cut -c1-60; done`
3. Resume labelling (in the background):
   `nohup scripts/run_labels.sh batches 10 haiku > data/run_labels.log 2>&1 &`
   (and `cbatches 4`, `sbatches 4`), then `nohup scripts/autocommit.sh >/dev/null 2>&1 &`. Create `data/` first (`mkdir -p data`).
4. ~~Topic taxonomy~~ DONE. To refresh after many new labels: regenerate `work/topics_raw.tsv` and have Sonnet extend `map`.
   (Old note:) Collect raw `topic` values with counts from `work/{labels,clabels,slabels}`. Have a Sonnet subagent map them to ~40 canonical topics → `work/topic_map.json` (raw → canonical). Make `served/build.py` apply it in `norm_topic` (unmapped → raw). Rebuild.
5. QA: a Sonnet re-label of ~3 random link batches, comparing keep agreement → `work/qa.md`. If Haiku is too loose or strict, adjust the threshold (`q`) in build.py.
6. Extend coverage if budget allows: the next 6,000 great-comment candidates (`served/comments.py`, raise N, write new batch numbers), and links with 3–4 distinct users (`served/batches.py 3`, but keep the existing numbering: only append new batches for URLs not yet covered).
7. Separate sections later: Wikipedia "rabbit holes" (most-linked articles), books (Amazon/Goodreads links → titles), GitHub repos.
8. Daily updates from the HN API, and deploy (owner to decide: GitHub Pages / VPS / domain).
9. Personalisation from browser history (Chrome/Safari) to re-rank the feed.

## Open questions for the owner
- Make the site public via GitHub Pages, or keep it private (VPS with auth / local only)?
- Wikipedia, books and GitHub repos as their own tabs?
