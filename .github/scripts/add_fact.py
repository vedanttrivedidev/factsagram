#!/usr/bin/env python3
"""Runs in GitHub Actions when the repo owner labels a suggestion issue 'approve'.

Reads the issue from the event payload file (never from shell text), validates it,
and appends it to facts.json. Writes a reply for the workflow to post on the issue.
"""
import json, os, re, sys
from pathlib import Path

event = json.load(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8"))
FACTS = Path("facts.json")
REPLY = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "reply.md"


def finish(status, message):
    REPLY.write_text(message, encoding="utf-8")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write(f"status={status}\n")
    sys.exit(0)


body = event["issue"].get("body") or ""
m_fact = re.search(r"^Fact:\s*(.+)$", body, re.M)
m_cat = re.search(r"^Category:\s*(.+)$", body, re.M)
if not m_fact:
    finish("rejected", "I couldn't find a `Fact:` line. Edit the issue so it has `Category: ...` and "
                       "`Fact: ...` lines, then add the `approve` label again.")

fact = re.sub(r"\s+", " ", m_fact.group(1)).strip()
cat = re.sub(r"[^\w &'-]", "", m_cat.group(1)).strip()[:24] if m_cat else ""
cat = cat or "Community"
if not 10 <= len(fact) <= 280:
    finish("rejected", "The fact must be between 10 and 280 characters. Edit the issue and re-apply `approve`.")

facts = json.loads(FACTS.read_text(encoding="utf-8"))
if any(str(f.get("fact", "")).strip().lower() == fact.lower() for f in facts):
    finish("rejected", "That fact is already in `facts.json`, so nothing was added.")

facts.append({"category": cat, "fact": fact, "source": "Community"})
FACTS.write_text(json.dumps(facts, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
finish("added", f"Approved and added to **{cat}**. It goes live in a minute or two. Thanks for the suggestion!")
