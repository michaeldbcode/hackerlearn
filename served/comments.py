"""Stage 5 prep: candidate great comments -> data/derived/comments_cand.parquet + work/cbatches/*.jsonl"""
import duckdb, html, json, os, re
c = duckdb.connect("data/derived/m.duckdb"); c.execute("set threads=4")
# citations: comments linking to news.ycombinator.com/item?id=N
c.execute("""create or replace table cites as
select try_cast(unnest(regexp_extract_all(text, 'item\\?id=(\\d{1,9})', 1)) as uinteger) id, "by" as author
from read_parquet('data/raw/*/*.parquet') where type=2 and text like '%item?id=%'""")
c.execute("""create or replace table cc as
select c.id, c.parent, c."by" author, c.time, c.text, coalesce(len(c.kids),0) nk, coalesce(x.nc,0) nc,
  length(c.text) - length(replace(c.text,' ','')) nwords
from read_parquet('data/raw/*/*.parquet') c
left join (select id, count(distinct author) nc from cites group by 1) x using(id)
where c.type=2 and coalesce(c.dead,0)=0 and coalesce(c.deleted,0)=0
  and (length(c.text) - length(replace(c.text,' ',''))) >= 200 and (coalesce(len(c.kids),0) >= 4 or coalesce(x.nc,0) >= 2)""")
print(c.execute("select count(*), sum((nc>=2)::int), sum((nk>=10)::int) from cc").fetchall())
import sys
N = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
SKIP = int(sys.argv[2]) if len(sys.argv) > 2 else 0  # append mode: skip the top SKIP (already batched)
rows = c.execute(f"""
select cc.id, cc.author, year(cc.time) y, cc.nk, cc.nc, cc.text, p.title
from cc left join (select id, title from read_parquet('data/raw/*/*.parquet') where type=1) p on p.id = cc.parent
order by cc.nc*6 + least(cc.nk, 40) + least(cc.nwords, 800)/40.0 desc limit {N} offset {SKIP}""").fetchall()
os.makedirs("work/cbatches", exist_ok=True)
def clean(t):
    t = re.sub(r"<p>", "\n", t); t = re.sub(r"<[^>]+>", "", t); return html.unescape(t).strip()
for b in range(0, N, 100):
    with open(f"work/cbatches/{(SKIP + b)//100:05d}.jsonl", "w") as f:
        for i, (cid, a, y, nk, nc, t, title) in enumerate(rows[b:b+100]):
            f.write(json.dumps({"id": cid, "by": a, "year": y, "replies": nk, "cited_by": nc, "story": title, "text": clean(t)[:1400]}, ensure_ascii=False) + "\n")
print("wrote", (N + 99)//100, "comment batches from", SKIP//100)
