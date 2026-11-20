"""Polite scraper for public pages of DarGlobal and Wasalt -> data/corpus.jsonl"""
import json, re, time, urllib.robotparser
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
import httpx
from bs4 import BeautifulSoup

SEEDS = {
    "DarGlobal": ["https://www.darglobal.co.uk", "https://www.darglobal.com"],
    "Wasalt": ["https://wasalt.com", "https://www.wasalt.com"],
}
MAX_PAGES = 60
UA = "Mozilla/5.0 (compatible; AssignmentBot/1.0)"
OUT = Path("data/corpus.jsonl")

def chunk(text, size=900):
    sents, cur, out = re.split(r"(?<=[.!?])\s+", text), "", []
    for s in sents:
        if len(cur) + len(s) > size and cur:
            out.append(cur.strip()); cur = ""
        cur += " " + s
    if cur.strip(): out.append(cur.strip())
    return out

def crawl(company, seeds, client):
    seen, q, rows = set(), deque(seeds), []
    hosts = {urlparse(s).netloc.replace("www.", "") for s in seeds}
    rp = {}
    while q and len(seen) < MAX_PAGES:
        url = urldefrag(q.popleft())[0]
        if url in seen: continue
        seen.add(url)
        host = urlparse(url).netloc
        if host not in rp:
            r = urllib.robotparser.RobotFileParser(f"https://{host}/robots.txt")
            try: r.read()
            except Exception: r = None
            rp[host] = r
        if rp[host] and not rp[host].can_fetch(UA, url): continue
        try:
            resp = client.get(url)
            if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""): continue
        except Exception: continue
        soup = BeautifulSoup(resp.text, "html.parser")
        for t in soup(["script", "style", "noscript", "nav", "footer", "svg", "form"]): t.decompose()
        title = (soup.title.string or "").strip() if soup.title else url
        text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
        for c in chunk(text):
            if len(c) > 80: rows.append({"company": company, "url": url, "title": title, "text": c})
        for a in soup.find_all("a", href=True):
            n = urldefrag(urljoin(url, a["href"]))[0]
            if urlparse(n).netloc.replace("www.", "") in hosts and not re.search(r"\.(pdf|jpg|png|zip|mp4)$", n, re.I):
                q.append(n)
        time.sleep(0.5)
    print(f"{company}: {len(seen)} pages, {len(rows)} chunks")
    return rows

if __name__ == "__main__":
    OUT.parent.mkdir(exist_ok=True)
    rows = []
    with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=15) as c:
        for co, seeds in SEEDS.items(): rows += crawl(co, seeds, c)
    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows))
    print("Saved", len(rows), "chunks")
