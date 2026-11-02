"""Stage 2 prep: build per-URL candidate batches -> work/batches/NNNNN.jsonl (sorted by distinct users desc)."""
import duckdb, html, json, os, re, sys

MIN_USERS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
MAX_USERS = int(sys.argv[2]) if len(sys.argv) > 2 else 10**9
START = int(sys.argv[3]) if len(sys.argv) > 3 else 0  # first batch number (append mode); ids continue from START*BATCH
BATCH = 200
REC = re.compile(r"best|recommend|great|excellent|classic|must.read|worth (reading|a read)|explain|intro|learn|favou?rite|brilliant|fantastic|good read|check out|seminal|definitive", re.I)
EXCL = "domain like '%wikipedia.org' or domain in ('github.com','amazon.com','amazon.co.uk','smile.amazon.com','goodreads.com','imdb.com','worldometers.info','hnsearch.com','statista.com','tiobe.com','addons.mozilla.org','chrome.google.com')"

def snippet(ctx, dom):
    ctx = html.unescape(ctx)
    i = ctx.find(dom)
    i = 0 if i < 0 else max(0, i - 220)
    return ctx[i:i + 380].strip()

c = duckdb.connect("data/derived/m.duckdb")
rows = c.execute(f"""
with a as (select u, any_value(domain) domain, count(distinct author) nu, min(year(time)) y0, max(year(time)) y1 from m group by u)
select u, domain, nu, y0, y1 from a where nu >= {MIN_USERS} and nu <= {MAX_USERS} and not ({EXCL}) order by nu desc, u""").fetchall()
ctx = {}
for u, author, dom, cx in c.execute(f"""
with a as (select u from m group by u having count(distinct author) between {MIN_USERS} and {MAX_USERS})
select m.u, author, domain, context from m join a using(u)""").fetchall():
    ctx.setdefault(u, {}).setdefault(author, (dom, cx))
os.makedirs("work/batches", exist_ok=True)
items = []
for n, (u, dom, nu, y0, y1) in enumerate(rows):
    cands = sorted(ctx[u].values(), key=lambda t: -bool(REC.search(t[1])))[:3]
    items.append({"id": START * BATCH + n, "url": u, "users": nu, "years": f"{y0}-{y1}", "snips": [snippet(cx, d) for d, cx in cands]})
for b in range(0, len(items), BATCH):
    with open(f"work/batches/{START + b // BATCH:05d}.jsonl", "w") as f:
        f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in items[b:b + BATCH])
print(len(items), "urls,", (len(items) + BATCH - 1) // BATCH, "batches")
