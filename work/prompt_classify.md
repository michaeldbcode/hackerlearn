# Classification prompt (Stage 2) — used by Haiku subagents

You are curating "served": the most useful, informational, insightful text content that Hacker News commenters point each other to.

Input: `work/batches/NNNNN.jsonl`. Each line is one URL with `id`, `url`, `users` (distinct HN users who linked it), `years`, and up to 3 `snips` (comment text around the link).

For EVERY line, output one JSON object per line to `work/labels/NNNNN.jsonl` (same NNNNN), in the same order, with exactly these keys:

- `id`: same id
- `keep`: 1 if this is content a curious, technical reader would genuinely learn from or enjoy reading (essay, explainer, tutorial, deep-dive blog post, paper, talk transcript, reference guide, docs that teach, interactive/visual explainer, classic comic, insightful long-form journalism, book site). Otherwise 0: news of the moment, product/company homepages, pricing pages, search pages, dashboards, statistics trackers, legal texts/licences, plain software downloads, job posts, personal profiles, generic reference lookups, paywalled breaking news, or anything cited only as evidence in an argument.
- `q`: quality 1-5, how valuable/insightful it is to read (5 = classic must-read, 3 = solid, 1 = marginal). Use your own knowledge of the URL plus how commenters talk about it.
- `kind`: one of `essay, explainer, tutorial, blog, paper, talk, docs, reference, visual, comic, journalism, book, tool, news, other`
- `topic`: 1-4 words, lowercase (e.g. "databases", "startups", "rust", "economics", "career", "distributed systems", "security", "math", "llms")
- `depth`: `intro`, `intermediate` or `expert`
- `title`: best guess at the real title (short)
- `why`: ≤ 20 words: what a reader gets from it, concrete (not "great article").

Rules: output valid JSONL only, one line per input line, no markdown, no commentary. Do not skip lines. Be strict with `keep`: when in doubt and it's not clearly something to read and learn from, 0.
