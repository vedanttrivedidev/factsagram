#!/usr/bin/env python3
"""Grow facts.json from Wikipedia's "Did you know..." archive (Wikipedia:Recent additions).

  python3 harvest_wikipedia.py                 add ~1000 new facts
  python3 harvest_wikipedia.py --target 300    add ~300

Needs internet; standard library only. Existing facts are kept; duplicates are skipped.
Wikipedia text is CC BY-SA 4.0, so harvested facts are tagged "source": "Wikipedia".
"""
import argparse, html, json, os, random, re, sys, tempfile, time, urllib.parse, urllib.request
from pathlib import Path

API = "https://en.wikipedia.org/w/api.php"
UA = "FactDropHarvester/1.0 (vedanttrivedi904@gmail.com)"
OUT = Path(__file__).resolve().parent / "facts.json"
KEYWORDS = {
    "Space": ["planet", "moon", "nasa", "asteroid", "galaxy", "telescope", "astronaut", "comet"],
    "Animals": ["species", "bird", "fish", "dog", "cat", "snake", "whale", "insect", "spider", "frog"],
    "Music": ["album", "song", "singer", "band", "opera", "symphony", "composer", "guitar"],
    "Food": ["food", "dish", "cheese", "wine", "beer", "cuisine", "recipe", "chocolate", "coffee"],
    "Tech": ["computer", "software", "internet", "video game", "programming", "robot", "website"],
    "Science": ["chemical", "physicist", "gene", "protein", "atom", "scientist", "virus", "fossil"],
    "History": ["war", "king", "queen", "emperor", "battle", "empire", "medieval", "ancient", "dynasty"],
}


def api(**params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": "2"})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
        return json.load(r)


def archive_pages():
    titles, cont = [], {}
    while True:
        d = api(action="query", list="allpages", apnamespace=4, apprefix="Recent additions/", aplimit=500, **cont)
        titles += [p["title"] for p in d["query"]["allpages"]]
        if "continue" not in d:
            return titles
        cont = d["continue"]


def hooks(page_html):
    for li in re.findall(r"<li>(.*?)</li>", page_html, re.S):
        t = html.unescape(re.sub(r"<[^>]+>", "", li))
        t = re.sub(r"\s*\((?:pictured|listen|watch)[^)]*\)", "", t, flags=re.I)
        t = re.sub(r"\s+", " ", t).strip()
        m = re.match(r"^(?:\.\.\.|…)\s*that\b", t)
        if m and t.endswith("?") and 50 <= len(t) <= 260:
            yield "Did you know that" + t[m.end():]


def categorize(text):
    low = text.lower()
    for cat, words in KEYWORDS.items():
        if any(re.search(r"\b" + w + r"s?\b", low) for w in words):
            return cat
    return "Random"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=1000, help="new facts to add")
    ap.add_argument("--per-page", type=int, default=40, help="max facts taken per archive page")
    args = ap.parse_args()
    facts = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []
    have = {f["fact"] for f in facts}
    titles = archive_pages()
    random.shuffle(titles)
    print(f"Found {len(titles)} archive pages. Harvesting...", flush=True)
    added = 0
    for title in titles:
        if added >= args.target:
            break
        try:
            page = api(action="parse", page=title, prop="text", redirects=1)["parse"]["text"]
        except Exception as e:
            print(f"  skip {title}: {e}", file=sys.stderr)
            continue
        got = [h for h in hooks(page) if h not in have]
        random.shuffle(got)
        for h in got[:args.per_page]:
            facts.append({"category": categorize(h), "fact": h, "source": "Wikipedia"})
            have.add(h)
            added += 1
        print(f"  {title}: total new {added}", flush=True)
        time.sleep(0.4)
    random.shuffle(facts)
    fd, tmp = tempfile.mkstemp(dir=OUT.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=0)
    os.replace(tmp, OUT)
    print(f"Done. Added {added}; facts.json now has {len(facts)} facts.")


if __name__ == "__main__":
    main()
