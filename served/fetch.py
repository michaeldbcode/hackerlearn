"""Stage 4: fetch kept links, extract title + readable excerpt -> work/pages.jsonl (append, resumable)."""
import asyncio, json, os, glob
import httpx, trafilatura

OUT = "work/pages.jsonl"
UA = "Mozilla/5.0 (compatible; served/0.1; +https://github.com/michaeldbcode/served)"

def kept():
    urls = {}
    for f in sorted(glob.glob("work/labels/*.jsonl")):
        B = {}
        for l in open(f.replace("labels", "batches")):
            x = json.loads(l); B[x["id"]] = x
        for l in open(f):
            try: y = json.loads(l)
            except Exception: continue
            if y.get("keep") == 1 and y.get("id") in B:
                urls[B[y["id"]]["url"]] = 1
    return list(urls)

async def one(cl, sem, url, out):
    async with sem:
        rec = {"url": url}
        try:
            r = await cl.get("https://" + url, timeout=20)
            rec["status"] = r.status_code
            if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
                h = r.text
                meta = trafilatura.extract_metadata(h)
                txt = trafilatura.extract(h, include_comments=False, include_tables=False) or ""
                rec.update(title=(meta.title if meta else None), author=(meta.author if meta else None),
                           date=(meta.date if meta else None), words=len(txt.split()), excerpt=txt[:2500])
            elif r.status_code == 200 and "pdf" in r.headers.get("content-type", ""):
                rec["pdf"] = True
        except Exception as e:
            rec["error"] = type(e).__name__
        out.write(json.dumps(rec, ensure_ascii=False) + "\n"); out.flush()

async def main():
    done = set()
    if os.path.exists(OUT):
        for l in open(OUT):
            try: done.add(json.loads(l)["url"])
            except Exception: pass
    todo = [u for u in kept() if u not in done]
    print(len(todo), "to fetch", flush=True)
    sem = asyncio.Semaphore(48)
    async with httpx.AsyncClient(headers={"User-Agent": UA}, follow_redirects=True, verify=os.environ.get("SSL_CERT_FILE", True)) as cl:
        with open(OUT, "a") as out:
            await asyncio.gather(*(one(cl, sem, u, out) for u in todo))

if __name__ == "__main__":
    asyncio.run(main())
