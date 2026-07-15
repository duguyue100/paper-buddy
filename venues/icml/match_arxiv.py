#!/usr/bin/env python3
# ponytail: arXiv title-match for each ICML 2026 spotlight paper.
# Strategy: query arxiv ti:"<title>"; score by normalized-title equality AND
# at least one author surname overlap. Saves matches to data/arxiv_matches.json.
# Reads data/papers.json. Polite 3s delay between arxiv hits.
import os, json, sys, time, urllib.request, urllib.parse, re
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
PAPERS = os.path.join(HERE, "data", "papers.json")
OUT = os.path.join(HERE, "data", "arxiv_matches.json")
UA = "paper-buddy/1.0 (mailto:research@example.com)"  # swap real mailto if re-running
DELAY = 3.0
ATOM = "{http://www.w3.org/2005/Atom}"


def norm(s):
    # alphanumeric-only, lowercased, for strict equality
    return "".join(ch.lower() for ch in s if ch.isalnum())


def surname(author_string):
    # arxiv authors are "First Last" — last whitespace-separated token
    return author_string.lower().split()[-1] if author_string.strip() else ""


def search_arxiv(title):
    """Return list of dicts: {arxiv_id, title, authors: [...]} per atom entry."""
    url = ("https://export.arxiv.org/api/query?search_query=ti:"
           + urllib.parse.quote(title) + "&max_results=5")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for k in range(3):
        try:
            data = urllib.request.urlopen(req, timeout=45).read()
            break
        except Exception as e:
            if k == 2:
                print(f"[err] arxiv query failed: {e}", file=sys.stderr)
                return []
            time.sleep(5 * (k + 1))
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    out = []
    for e in root.findall(f"{ATOM}entry"):
        aid_full = e.findtext(f"{ATOM}id", "") or ""
        m = re.search(r"(\d{4}\.\d{4,5})", aid_full)
        if not m:
            continue
        out.append({
            "arxiv_id": m.group(1),
            "title": (e.findtext(f"{ATOM}title", "") or "").strip(),
            "authors": [a.findtext(f"{ATOM}name", "") or "" for a in e.findall(f"{ATOM}author")],
        })
    return out


def match_one(paper):
    or_title = paper["title"]
    or_authors = paper["authors"] or []
    or_surnames = {surname(a) for a in or_authors[:5] if surname(a)}
    candidates = search_arxiv(or_title)
    for c in candidates:
        if norm(or_title) == norm(c["title"]) and any(
            surname(ax) in or_surnames for ax in c["authors"] if ax.strip()
        ):
            return c["arxiv_id"]
    return None


def main():
    papers = json.load(open(PAPERS))
    # resume support — if OUT exists, skip already-decided ids
    existed = {}
    if os.path.exists(OUT):
        existed = {m["paper_id"]: m for m in json.load(open(OUT))}
    results = list(existed.values())
    done = set(existed.keys())
    todo = [p for p in papers if p["id"] not in done]
    print(f"[resume] {len(done)} already matched, {len(todo)} to search", file=sys.stderr)
    matched = 0
    for i, p in enumerate(todo, 1):
        aid = match_one(p)
        rec = {"paper_id": p["id"], "number": p["number"], "title": p["title"],
               "arxiv_id": aid}
        results.append(rec)
        if aid:
            matched += 1
            print(f"[{i}/{len(todo)}] OK   {p['number']:5d} {p['title'][:55]:55s} -> {aid}",
                  file=sys.stderr)
        else:
            print(f"[{i}/{len(todo)}] MISS {p['number']:5d} {p['title'][:55]:55s}",
                  file=sys.stderr)
        # write every 10 papers so resume is cheap
        if i % 10 == 0:
            with open(OUT, "w") as f:
                json.dump(results, f, indent=2)
        time.sleep(DELAY)
    with open(OUT, "w") as f:
        json.dump(results, f, indent=2)
    total_ok = sum(1 for r in results if r["arxiv_id"])
    print(f"[done] {total_ok}/{len(papers)} matched on arXiv (saved {OUT})",
          file=sys.stderr)


if __name__ == "__main__":
    main()