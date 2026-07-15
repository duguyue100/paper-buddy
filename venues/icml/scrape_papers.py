#!/usr/bin/env python3
# ponytail: pull ICML 2026 spotlight paper metadata via openreview-py -> data/papers.json
# login uses EMAIL/PASSWORD from .env (loaded via python-dotenv, which is installed).
import os, json, sys, time
from dotenv import load_dotenv
import openreview

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))
OUT = os.path.join(HERE, "data", "papers.json")

UA = "paper-buddy/1.0 (mailto:research@example.com)"  # placeholder; openreview-py ignores it


def login():
    for k in range(4):
        try:
            c = openreview.api.OpenReviewClient(
                baseurl="https://api2.openreview.net",
                username=os.environ["EMAIL"],
                password=os.environ["PASSWORD"],
            )
            return c
        except openreview.openreview.OpenReviewException as e:
            if "RateLimit" in str(e):
                wait = int(e.args[0].get("details", {}).get("resetTime") and 30 or 30)
                print(f"[rate-limit] login retry in {wait}s", file=sys.stderr)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("login failed after 4 attempts")


def val(field):
    """openreview v2 wraps content values as {'value': ...}; unwrap."""
    return field.get("value") if isinstance(field, dict) else field


def main():
    c = login()
    notes = c.get_all_notes(
        invitation="ICML.cc/2026/Conference/-/Submission",
        content={"venue": "ICML 2026 spotlight"},
    )
    print(f"[ok] {len(notes)} spotlight submissions", file=sys.stderr)
    papers = []
    for n in notes:
        papers.append({
            "id": n.id,
            "forum": n.id,
            "number": n.number,
            "title": val(n.content.get("title")),
            "authors": val(n.content.get("authors")),
            "authorids": val(n.content.get("authorids")),
            "abstract": val(n.content.get("abstract")),
            "primary_area": val(n.content.get("primary_area")),
            "keywords": val(n.content.get("keywords")),
            "tldr": val(n.content.get("TLDR")),
            "pdf": val(n.content.get("pdf")),  # /pdf/<hash>.pdf on openreview
            "venue": val(n.content.get("venue")),
            "paperhash": val(n.content.get("paperhash")),
        })
    # stable sort by paper number (icml submission ids)
    papers.sort(key=lambda p: (p["number"] or 0))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(papers, f, indent=2)
    print(f"[done] wrote {len(papers)} papers -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()