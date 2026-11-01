"""Stage 1: extract link mentions from comments -> data/derived/mentions/YYYY-MM.parquet"""
import duckdb, glob, os, sys
from concurrent.futures import ProcessPoolExecutor

OUT = "data/derived/mentions"
BLOCK = r"(^|\.)(youtube\.com|youtu\.be|vimeo\.com|twitter\.com|x\.com|t\.co|facebook\.com|fb\.com|instagram\.com|reddit\.com|redd\.it|linkedin\.com|bit\.ly|goo\.gl|tinyurl\.com|amzn\.to|ow\.ly|news\.ycombinator\.com|ycombinator\.com|imgur\.com|i\.imgur\.com|giphy\.com|google\.com|lmgtfy\.com|apple\.com|play\.google\.com|tiktok\.com|archive\.ph|archive\.is|archive\.today|threads\.net|bsky\.app|mastodon\.social|discord\.gg|discord\.com|pastebin\.com|gist\.github\.com|localhost|example\.com|hn\.algolia\.com|dropbox\.com|drive\.google\.com|docs\.google\.com)$"

SQL = r"""
with c as (
  select id, parent, "by" as author, time, text, coalesce(len(kids),0) as n_kids
  from read_parquet('{f}') where type=2 and coalesce(dead,0)=0 and coalesce(deleted,0)=0 and text like '%href=%'
), u as (
  select *, unnest(regexp_extract_all(text, 'href="([^"]+)"', 1)) as raw from c
), n as (
  select id as comment_id, parent, author, time, n_kids, text,
    replace(replace(replace(replace(raw,'&#x2F;','/'),'&amp;','&'),'&#x3D;','='),'&#x27;','''') as url
  from u
), h as (
  select *, regexp_replace(url, '^https?://web\.archive\.org/web/[0-9a-z_*]+/', '') as u1 from n
), z as (
  select *,
    lower(regexp_replace(regexp_extract(u1, '^(?:https?://)?([^/?#:]+)', 1), '^(www\d*|m|mobile|amp)\.', '')) as domain,
    regexp_replace(regexp_replace(regexp_replace(regexp_extract(u1, '^(?:https?://)?[^/?#]+(/[^#]*)?', 1),
      '[?&](utm_[a-z]+|ref|ref_src|fbclid|gclid|source|s|share)=[^&]*', '', 'g'), '\?$', ''), '/+$', '') as path
  from h
)
select comment_id, parent, author, time, n_kids, domain, path,
  domain || path as url_norm,
  left(regexp_replace(regexp_replace(text, '<[^>]+>', ' ', 'g'), '\s+', ' ', 'g'), 1500) as context
from z
where domain like '%.%' and not regexp_matches(domain, '{block}')
  and path <> '' and not regexp_matches(lower(path), '\.(png|jpe?g|gif|webp|svg|mp4|mp3)$')
"""

def run(f):
    name = os.path.basename(f)
    dst = os.path.join(OUT, name)
    if os.path.exists(dst): return
    con = duckdb.connect(); con.execute("set threads=2")
    con.sql(SQL.format(f=f, block=BLOCK)).write_parquet(dst + ".tmp")
    os.replace(dst + ".tmp", dst); print("ok", name, flush=True)

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    files = sorted(glob.glob("data/raw/*/*.parquet"))
    with ProcessPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 3) as ex:
        list(ex.map(run, files))
