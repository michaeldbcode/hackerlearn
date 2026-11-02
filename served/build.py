"""Stage 3+7: merge labels + pages into site/data/*.json"""
import glob, json, math, os, re, collections

def jl(p):
    out = []
    for l in open(p):
        try: out.append(json.loads(l))
        except Exception: pass
    return out

def join(bdir, ldir):
    rows = []
    for f in sorted(glob.glob(f"work/{ldir}/*.jsonl")):
        B = {x["id"]: x for x in jl(f.replace(ldir, bdir))}
        for y in jl(f):
            if isinstance(y, dict) and y.get("keep") == 1 and y.get("id") in B:
                rows.append({**B[y["id"]], **{k: v for k, v in y.items() if k != "id"}, "id": y["id"]})
    return rows

def reflow(t):
    lines = [l for l in t.split("\n")]
    if lines and sum(len(l) for l in lines) / max(1, len(lines)) < 90:
        t = re.sub(r"(?<![.!?:])\n(?!\n)", " ", t)
    return re.sub(r"\n{2,}", "\n\n", t).strip()

def norm_topic(t):
    t = (t or "other").lower().strip()
    return re.sub(r"\s+", " ", t)[:40]

os.makedirs("docs/data/ex", exist_ok=True)
pages = {p["url"]: p for p in jl("work/pages.jsonl")} if os.path.exists("work/pages.jsonl") else {}

# links
links = []
for r in join("batches", "labels"):
    p = pages.get(r["url"], {})
    q = int(r.get("q") or 3)
    if q < 2: continue
    title = r.get("title") or p.get("title") or r["url"]
    snip = next((s for s in r.get("snips", []) if re.search(r"recommend|best|great|excellent|classic|must|worth|favou?rite", s, re.I)), (r.get("snips") or [""])[0])
    links.append({"t": title[:160], "u": "https://" + r["url"], "d": r["url"].split("/")[0], "n": r["users"], "y": r["years"],
                  "k": r.get("kind", "other"), "p": norm_topic(r.get("topic")), "lv": r.get("depth", ""), "q": q, "w": r.get("why", ""),
                  "s": round(q * 2 + math.log2(r["users"] + 1) - (1.5 if r.get("kind") == "comic" else 0), 3), "ex": reflow(p.get("excerpt") or "")[:1800], "qt": snip[:380],
                  "wc": p.get("words", 0)})
# comments
comments = []
for r in join("cbatches", "clabels"):
    q = int(r.get("q") or 3)
    if q < 3: continue
    comments.append({"t": r.get("title", "")[:160], "u": f"https://news.ycombinator.com/item?id={r['id']}", "d": "comment by " + r["by"],
                     "n": r["replies"], "c": r["cited_by"], "y": str(r["year"]), "k": "comment", "p": norm_topic(r.get("topic")),
                     "q": q, "w": r.get("why", ""), "st": r.get("story") or "", "ex": r["text"], "s": round(q * 2 + math.log2(r["replies"] + 2 * r["cited_by"] + 1), 3)})
# stories
stories = []
for r in join("sbatches", "slabels"):
    q = int(r.get("q") or 3)
    if q < 3: continue
    stories.append({"t": r["title"], "u": f"https://news.ycombinator.com/item?id={r['id']}", "d": r["domain"], "n": r["points"], "c": r["comments"],
                    "y": str(r["year"]), "k": r.get("kind", "other"), "p": norm_topic(r.get("topic")), "q": q, "w": r.get("text", "")[:300],
                    "s": round(q * 2 + math.log2(r["points"] + 1), 3)})

def emit(name, items):
    items.sort(key=lambda x: -x["s"])
    idx = []
    for i, x in enumerate(items):
        x["i"] = i
        ex = {k: x.pop(k) for k in ("ex", "qt", "st") if k in x}
        if ex:
            ch = f"docs/data/ex/{name}-{i // 250}.json"
            idx.append((ch, i, ex))
    chunks = collections.defaultdict(dict)
    for ch, i, ex in idx: chunks[ch][i] = ex
    for ch, d in chunks.items(): open(ch, "w").write(json.dumps(d, ensure_ascii=False).replace("\ufffd", ""))
    open(f"docs/data/{name}.json", "w").write(json.dumps(items, ensure_ascii=False, separators=(",", ":")).replace("\ufffd", ""))
    print(name, len(items))

emit("links", links); emit("comments", comments); emit("stories", stories)
topics = collections.Counter(x["p"] for x in links + comments + stories)
json.dump([t for t, n in topics.most_common() if n >= 8][:120], open("docs/data/topics.json", "w"))
