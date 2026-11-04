#!/usr/bin/env python3
"""FactDrop: 2-3 random fun-fact notifications a day. Python 3.9+, standard library only.

  python3 factdrop.py          run (leave it open, or start it at login)
  python3 factdrop.py --test   send one notification now and exit
"""
import hashlib, json, os, random, subprocess, sys, tempfile, time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FACTS_FILE, STATE_FILE = ROOT / "facts.json", ROOT / "state.json"
START_HOUR, END_HOUR = 9, 21          # local time window for notifications
MIN_PER_DAY, MAX_PER_DAY = 2, 3
MIN_GAP = timedelta(minutes=90)       # minimum spacing between notifications
MAX_LATE = timedelta(minutes=30)      # skip notifications missed by more than this (e.g. laptop asleep)
TICK_SECONDS = 20


def fact_id(text):
    """Stable ID, so editing/reordering facts.json never breaks saved state."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def load_facts():
    try:
        raw = json.loads(FACTS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.exit(f"Could not read {FACTS_FILE.name}: {e}")
    facts = {}
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict) and item.get("fact"):
            facts[fact_id(item["fact"])] = (item.get("category", "Fact"), item["fact"])
    if not facts:
        sys.exit(f'{FACTS_FILE.name} must be a list like [{{"category": "Space", "fact": "..."}}]')
    return facts


def load_state():
    try:
        s = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return {"sent": list(s.get("sent", [])), "date": s.get("date"), "schedule": list(s.get("schedule", []))}
    except (OSError, ValueError, AttributeError):
        return {"sent": [], "date": None, "schedule": []}


def save_state(state):
    """Atomic write: a crash mid-save can't corrupt state.json."""
    fd, tmp = tempfile.mkstemp(dir=ROOT, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def notify(title, msg):
    """Native notification. Text is passed as arguments or env vars, never spliced into code."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["osascript", "-e", "on run argv",
                            "-e", "display notification (item 1 of argv) with title (item 2 of argv)",
                            "-e", "end run", msg, title], check=False, timeout=15)
            return
        if sys.platform.startswith("linux"):
            subprocess.run(["notify-send", "-a", "FactDrop", "--", title, msg], check=False, timeout=15)
            return
        if sys.platform == "win32":
            ps = ("Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
                  "$n=New-Object System.Windows.Forms.NotifyIcon;"
                  "$n.Icon=[System.Drawing.SystemIcons]::Information;"
                  "$n.BalloonTipTitle=$env:FD_TITLE;$n.BalloonTipText=$env:FD_MSG;"
                  "$n.Visible=$true;$n.ShowBalloonTip(10000);Start-Sleep -Seconds 11;$n.Dispose()")
            subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                             env={**os.environ, "FD_TITLE": title, "FD_MSG": msg[:250]},
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
    except (OSError, subprocess.SubprocessError):
        pass
    print(f"\n🔔 {title}\n{msg}\n", flush=True)   # fallback: no notifier available


def plan_day(facts, state, now):
    """Pick today's times and facts. Always records the date, so this runs once per day."""
    start = max(now + timedelta(minutes=1), now.replace(hour=START_HOUR, minute=0, second=0, microsecond=0))
    end = now.replace(hour=END_HOUR, minute=0, second=0, microsecond=0)
    span = int((end - start).total_seconds() // 60)
    slots = []
    if span > 0:
        want = random.randint(MIN_PER_DAY, MAX_PER_DAY)
        for _ in range(300):
            c = start + timedelta(minutes=random.randrange(span))
            if all(abs(c - o) >= MIN_GAP for o in slots):
                slots.append(c)
            if len(slots) == want:
                break
    slots.sort()
    sent = set(state["sent"])
    pool = [i for i in facts if i not in sent]
    if len(pool) < len(slots):               # seen everything: start a new cycle
        state["sent"], pool = [], list(facts)
    picks = random.sample(pool, min(len(slots), len(pool)))
    state["date"] = now.date().isoformat()
    state["schedule"] = [{"at": s.isoformat(timespec="seconds"), "id": i, "done": False}
                         for s, i in zip(slots, picks)]
    save_state(state)


def main():
    facts = load_facts()
    if "--test" in sys.argv:
        cat, text = random.choice(list(facts.values()))
        notify(f"FactDrop • {cat}", text)
        print(f"{cat}: {text}")
        return
    state = load_state()
    print("FactDrop is running: 2-3 facts a day between "
          f"{START_HOUR}:00 and {END_HOUR}:00. Ctrl+C to stop.", flush=True)
    try:
        while True:
            now = datetime.now()
            if state["date"] != now.date().isoformat():
                plan_day(facts, state, now)
            changed = False
            for item in state["schedule"]:
                if item["done"] or now < datetime.fromisoformat(item["at"]):
                    continue
                item["done"], changed = True, True
                if now - datetime.fromisoformat(item["at"]) > MAX_LATE or item["id"] not in facts:
                    continue                  # missed it (asleep) or fact was removed
                cat, text = facts[item["id"]]
                notify(f"FactDrop • {cat}", text)
                print(f"[{now:%H:%M}] {cat}: {text}", flush=True)
                state["sent"].append(item["id"])
            if changed:
                save_state(state)
            time.sleep(TICK_SECONDS)
    except KeyboardInterrupt:
        print("\nFactDrop stopped.")


if __name__ == "__main__":
    main()
