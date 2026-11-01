# Great-comments prompt (Stage 5) — used by Haiku workers

You are curating "served": the most insightful, informational comments ever written on Hacker News.

Input: `work/cbatches/NNNNN.jsonl`. Each line is one HN comment with `id`, `by`, `year`, `replies`, `cited_by` (how many other users linked to this comment), `story` (thread title, may be null), `text`.

For EVERY line output one JSON object per line to `work/clabels/NNNNN.jsonl`, same order, keys:

- `id`: same id
- `keep`: 1 if a curious technical reader would genuinely learn something from this comment on its own: a substantive explanation, first-hand expert experience, a clear mental model, historical insider knowledge, a great practical guide, or a superb list of resources. 0 for: arguments/flame wars, opinions without substance, politics rants, jokes, moderation notes, personal anecdotes with no lesson, replies that only make sense in context.
- `q`: 1-5 how valuable it is (5 = classic, people should bookmark it).
- `topic`: 1-4 words lowercase.
- `title`: a short headline (≤ 10 words) for what the comment teaches, e.g. "How CPU branch predictors actually work".
- `why`: ≤ 25 words: the key insight/takeaway, concrete.

Output valid JSONL only, one line per input line. Do not skip lines. Be strict.
