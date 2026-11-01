"""Stage 0: download all monthly parquet files of open-index/hacker-news into data/raw/."""
import json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

REPO = "open-index/hacker-news"
API = f"https://huggingface.co/api/datasets/{REPO}/tree/main/data"
RAW = f"https://huggingface.co/datasets/{REPO}/resolve/main/"
OUT = "data/raw"
HDR = {"Authorization": f"Bearer {os.environ['HF_TOKEN']}"} if os.environ.get("HF_TOKEN") else {}

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=120)

def list_files():
    years = [d["path"] for d in json.load(get(API)) if d["type"] == "directory"]
    files = []
    for y in years:
        files += [(f["path"], f.get("size", 0)) for f in json.load(get(f"https://huggingface.co/api/datasets/{REPO}/tree/main/{y}")) if f["path"].endswith(".parquet")]
    return files

def fetch(item):
    path, size = item
    dst = os.path.join(OUT, path.removeprefix("data/"))
    if os.path.exists(dst) and (not size or os.path.getsize(dst) == size):
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    for attempt in range(5):
        try:
            with get(RAW + path) as r, open(dst + ".part", "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            os.replace(dst + ".part", dst)
            print("ok", path, flush=True)
            return
        except Exception as e:
            print("retry", path, e, flush=True)
            time.sleep(2 ** attempt)
    print("FAILED", path, flush=True)

if __name__ == "__main__":
    files = list_files()
    print(len(files), "files,", round(sum(s for _, s in files) / 1e9, 2), "GB", flush=True)
    with ThreadPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as ex:
        list(ex.map(fetch, files))
