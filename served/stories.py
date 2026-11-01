"""Stage 6 prep: notable stories (score>=300, comments>=100) -> work/sbatches/*.jsonl"""
import duckdb, html, json, os, re
c = duckdb.connect()
rows = c.execute("""select id, title, url, score, descendants, year(time) y, "by", left(text, 400)
from read_parquet('data/raw/*/*.parquet') where type=1 and score>=300 and descendants>=100 order by score desc""").fetchall()
os.makedirs("work/sbatches", exist_ok=True)
for b in range(0, len(rows), 400):
    with open(f"work/sbatches/{b//400:05d}.jsonl", "w") as f:
        for (i, t, u, s, d, y, a, tx) in rows[b:b+400]:
            dom = re.sub(r"^(https?://)?(www\.)?([^/]+).*", r"\3", u) if u else "news.ycombinator.com"
            x = {"id": i, "title": html.unescape(t or ""), "domain": dom, "year": y, "points": s, "comments": d}
            if tx: x["text"] = html.unescape(re.sub(r"<[^>]+>", " ", tx))[:300]
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
print(len(rows), "stories")
