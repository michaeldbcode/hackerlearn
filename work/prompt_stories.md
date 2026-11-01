# Notable-stories prompt (Stage 6) — used by Haiku workers

You are curating "served": the most informational, insightful Hacker News front-page stories of all time.

Input: `work/sbatches/NNNNN.jsonl`. Each line: `id`, `title`, `domain`, `year`, `points`, `comments`, optional `text` (for Ask/Show HN).

For EVERY line output one JSON object per line to `work/slabels/NNNNN.jsonl`, same order, keys:
- `id`: same id
- `keep`: 1 if it's something a curious technical reader would still learn from today: deep-dives, explainers, essays, post-mortems, research, insightful Ask HN threads, historically significant technical writeups, great Show HN projects with interesting technical writing. 0 for: transient news (acquisitions, layoffs, lawsuits, outages, product launches, deaths, politics, funding, company drama), pure announcements, memes.
- `q`: 1-5 lasting value.
- `kind`: one of `essay, explainer, tutorial, blog, paper, postmortem, ask_hn, show_hn, journalism, history, other`
- `topic`: 1-4 words lowercase.

Output valid JSONL only, one line per input line, no commentary. Be strict.
