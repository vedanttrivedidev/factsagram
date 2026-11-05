#!/usr/bin/env python3
"""Grow facts.json from Wikipedia's "Did you know..." archive (Wikipedia:Recent additions).

  python3 harvest_wikipedia.py                 add ~1000 new facts
  python3 harvest_wikipedia.py --target 300    add ~300

Needs internet; standard library only. Existing facts are kept; duplicates are skipped.
Wikipedia text is CC BY-SA 4.0, so harvested facts are tagged "source": "Wikipedia".
"""
import argparse, html, json, os, random, re, sys, tempfile, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

API = "https://en.wikipedia.org/w/api.php"
UA  = "FactDropHarvester/1.1 (+https://github.com/vedanttrivedidev/factsagram)"   # --email adds your address
OUT = Path(__file__).resolve().parent / "facts.json"

# --- Category keywords: broad, covering essentially all general topics ---
KEYWORDS = {
    "Space":        ["planet", "moon", "nasa", "asteroid", "galaxy", "telescope",
                     "astronaut", "comet", "orbit", "solar system", "nebula", "satellite",
                     "spacecraft", "rocket", "mars", "venus", "jupiter", "saturn"],
    "Animals":      ["species", "bird", "fish", "dog", "cat", "snake", "whale", "insect",
                     "spider", "frog", "mammal", "reptile", "amphibian", "primate",
                     "dinosaur", "shark", "eagle", "wolf", "bear", "penguin", "dolphin"],
    "Plants":       ["plant", "tree", "flower", "fungi", "mushroom", "seed", "forest",
                     "grass", "moss", "fern", "cactus", "orchid", "algae", "vine", "fruit"],
    "History":      ["war", "king", "queen", "emperor", "battle", "empire", "medieval",
                     "ancient", "dynasty", "revolution", "civilization", "pharaoh",
                     "colonial", "century", "parliament", "treaty", "republic", "throne",
                     "gladiator", "crusade", "plague", "expedition", "explorer"],
    "Science":      ["chemical", "physicist", "gene", "protein", "atom", "scientist",
                     "virus", "fossil", "element", "molecule", "reaction", "laboratory",
                     "experiment", "hypothesis", "evolution", "cell", "bacteria",
                     "isotope", "neuron", "vaccine", "dna", "enzyme"],
    "Physics":      ["gravity", "quantum", "electron", "photon", "relativity", "energy",
                     "force", "particle", "mass", "speed of light", "nuclear", "magnetic",
                     "thermodynamics", "entropy", "wave", "laser", "radiation"],
    "Math":         ["mathematician", "theorem", "prime", "equation", "geometry",
                     "calculus", "pi", "infinity", "proof", "fibonacci", "fractal",
                     "algorithm", "number", "matrix", "topology"],
    "Geography":    ["country", "continent", "ocean", "river", "mountain", "island",
                     "desert", "lake", "volcano", "canyon", "rainforest", "glacier",
                     "peninsula", "archipelago", "capital", "border", "territory"],
    "Food":         ["food", "dish", "cheese", "wine", "beer", "cuisine", "recipe",
                     "chocolate", "coffee", "spice", "bread", "fruit", "vegetable",
                     "restaurant", "chef", "ingredient", "baking", "feast", "harvest"],
    "Music":        ["album", "song", "singer", "band", "opera", "symphony", "composer",
                     "guitar", "piano", "orchestra", "jazz", "blues", "classical",
                     "instrument", "concert", "melody", "rhythm", "conductor"],
    "Art":          ["painting", "sculptor", "artwork", "museum", "canvas", "portrait",
                     "architecture", "mural", "exhibition", "gallery", "renaissance",
                     "impressionist", "abstract", "installation", "drawing", "sketch"],
    "Literature":   ["novel", "poet", "author", "book", "story", "fiction", "play",
                     "character", "narrative", "chapter", "essay", "literary", "prose",
                     "mythology", "folklore", "fable", "legend", "manuscript"],
    "Film & TV":    ["film", "movie", "director", "actor", "actress", "cinema",
                     "television", "series", "animation", "documentary", "oscar",
                     "screenplay", "sequel", "studio", "broadcast"],
    "Sports":       ["sport", "athlete", "championship", "olympic", "football", "soccer",
                     "cricket", "tennis", "basketball", "baseball", "swimming",
                     "marathon", "tournament", "medal", "stadium", "coach", "referee"],
    "Tech":         ["computer", "software", "internet", "video game", "programming",
                     "robot", "website", "invention", "patent", "engineer", "satellite",
                     "smartphone", "artificial intelligence", "processor", "network",
                     "database", "code", "algorithm", "startup"],
    "Psychology":   ["brain", "mind", "behaviour", "behavior", "cognitive", "memory",
                     "emotion", "phobia", "dream", "sleep", "perception", "instinct",
                     "personality", "language", "learning", "illusion"],
    "Economics":    ["economy", "trade", "market", "currency", "bank", "inflation",
                     "investment", "tax", "wealth", "poverty", "industry", "commerce",
                     "stock", "gdp", "entrepreneur", "monopoly"],
    "Politics":     ["government", "president", "prime minister", "election", "democracy",
                     "constitution", "parliament", "senate", "diplomat", "policy",
                     "legislation", "vote", "party", "nation", "independence"],
    "Religion":     ["religion", "temple", "church", "mosque", "cathedral", "ritual",
                     "deity", "myth", "prayer", "pilgrimage", "saint", "holy",
                     "scripture", "monastery", "prophet"],
    "Language":     ["word", "language", "alphabet", "grammar", "dialect", "translation",
                     "etymology", "slang", "phonetic", "script", "symbol", "linguistics"],
    "Body":         ["heart", "lung", "bone", "muscle", "blood", "nerve", "brain",
                     "organ", "skeleton", "dna", "hormone", "immune", "anatomy",
                     "surgery", "medicine", "doctor", "disease"],
    "Inventions":   ["invention", "inventor", "patent", "discover", "innovate",
                     "prototype", "machine", "device", "engine", "tool", "mechanism"],
    "Nature":       ["climate", "weather", "storm", "earthquake", "tsunami", "rainfall",
                     "ecosystem", "habitat", "migration", "season", "tide", "phenomenon"],
    "Transport":    ["ship", "aircraft", "train", "car", "bridge", "road", "port",
                     "airline", "submarine", "tunnel", "highway", "railway"],
    "Architecture": ["building", "skyscraper", "monument", "castle", "palace", "tower",
                     "bridge", "dome", "pyramid", "cathedral", "temple", "ruins"],
    "Mythology":    ["myth", "legend", "god", "goddess", "hero", "dragon", "giant",
                     "oracle", "titan", "olympus", "folklore", "creature"],
    "Fashion":      ["fashion", "clothing", "textile", "designer", "fabric", "style",
                     "costume", "trend", "accessories", "jewellery", "jewelry"],
    "Education":    ["university", "school", "scholar", "student", "degree", "research",
                     "library", "academic", "professor", "curriculum"],
    "Law":          ["law", "court", "judge", "trial", "crime", "justice", "lawyer",
                     "constitution", "verdict", "prison", "rights"],
    "Funny":        ["coincidence", "accident", "unexpected", "ironic", "peculiar",
                     "bizarre", "quirky", "odd", "strange", "unusual", "absurd"],
    "AI":           ["artificial intelligence", "machine learning", "neural network",
                     "robot", "algorithm", "automation", "chatbot", "deep learning"],
    "Environment":  ["pollution", "recycling", "renewable", "carbon", "biodiversity",
                     "conservation", "endangered", "habitat", "deforestation", "ocean"],
}

# --- Facts containing any of these phrases are skipped entirely ---
BLOCK = re.compile(
    r"\b(affair|adultery|mistress|infidelity|lover|extramarital|cheat(?:ed|ing)|"
    r"prostitut|brothel|pornograph|erotic|sexual assault|rape|molest|"
    r"nude|nudity|naked|obscen|indecent|strip)\b",
    re.I,
)


def api(**params):
    """GET the Wikipedia API, backing off and retrying when rate limited (HTTP 429/503)."""
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": "2"})
    wait = 5
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or attempt == 5:
                raise
            ra = e.headers.get("Retry-After", "")
            pause = min(int(ra), 300) if ra.isdigit() else wait
            print(f"  rate limited (HTTP {e.code}); waiting {pause}s, then retrying...", flush=True)
            time.sleep(pause)
            wait = min(wait * 2, 120)


def archive_pages():
    titles, cont = [], {}
    while True:
        d = api(action="query", list="allpages", apnamespace=4,
                apprefix="Recent additions/", aplimit=500, **cont)
        titles += [p["title"] for p in d["query"]["allpages"]]
        if "continue" not in d:
            return titles
        cont = d["continue"]


def hooks(page_html, stats=None):
    for li in re.findall(r"<li>(.*?)</li>", page_html, re.S):
        t = html.unescape(re.sub(r"<[^>]+>", "", li))
        t = re.sub(r"\s*\((?:pictured|listen|watch)[^)]*\)", "", t, flags=re.I)
        t = re.sub(r"\s+", " ", t).strip()
        m = re.match(r"^(?:\.\.\.|…)\s*that\b", t, re.I)
        if not m:
            continue
        fact = "Did you know that" + t[m.end():]
        # Must end with ? and be a sensible length
        if not fact.endswith("?") or not (50 <= len(fact) <= 300):
            continue
        # Skip anything touching blocked topics
        if BLOCK.search(fact):
            if stats is not None:
                stats["blocked"] += 1
            continue
        yield fact


def categorize(text):
    low = text.lower()
    for cat, words in KEYWORDS.items():
        if any(re.search(r"\b" + re.escape(w) + r"s?\b", low) for w in words):
            return cat
    return "Random"


def save(facts):
    fd, tmp = tempfile.mkstemp(dir=OUT.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=0)
    os.replace(tmp, OUT)


def main():
    global UA
    ap = argparse.ArgumentParser(description="Harvest Wikipedia Did-you-know facts into facts.json")
    ap.add_argument("--target",   type=int,   default=1000, help="new facts to add (default 1000)")
    ap.add_argument("--per-page", type=int,   default=50,   help="max facts taken per archive page (default 50)")
    ap.add_argument("--delay",    type=float, default=1.5,  help="seconds between requests (default 1.5)")
    ap.add_argument("--email",    default="",               help="your contact email, added to the User-Agent")
    args = ap.parse_args()
    if args.email:
        UA = UA.replace(")", f"; {args.email})")

    facts = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []
    have = {f["fact"] for f in facts}
    titles = archive_pages()
    random.shuffle(titles)
    print(f"Found {len(titles)} archive pages. Harvesting up to {args.target} new facts...", flush=True)

    added, stats, fails = 0, {"blocked": 0}, 0
    try:
        for n, title in enumerate(titles, 1):
            if added >= args.target:
                break
            try:
                page = api(action="parse", page=title, prop="text", redirects=1)["parse"]["text"]
                fails = 0
            except Exception as e:
                fails += 1
                print(f"  skip {title}: {e}", file=sys.stderr)
                if fails >= 5:
                    print("Too many failures in a row. Wait ~15 minutes and run again; progress is saved.")
                    break
                time.sleep(args.delay * 4)
                continue
            new = [h for h in hooks(page, stats) if h not in have]
            random.shuffle(new)
            for h in new[:args.per_page]:
                if added >= args.target:
                    break
                facts.append({"category": categorize(h), "fact": h, "source": "Wikipedia"})
                have.add(h)
                added += 1
            print(f"  {title}: total new {added}", flush=True)
            if n % 10 == 0:
                save(facts)                      # checkpoint so a long run is never lost
            time.sleep(args.delay)
    except KeyboardInterrupt:
        print("\nStopped early; saving what was collected...")

    random.shuffle(facts)
    save(facts)
    print(f"Done. Added {added} facts ({stats['blocked']} filtered out). facts.json now has {len(facts)} total.")


if __name__ == "__main__":
    main()
