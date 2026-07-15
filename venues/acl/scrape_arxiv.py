#!/usr/bin/env python3
# ponytail: match ACL 2026 oral papers to arXiv (strict normalized-title equality
# + author-surname confirmation), then download the LaTeX e-print tarballs.
# ACL doesn't publish reviews, so this is the only corpus-build step besides
# extract/aggregate. Reads data/oral_papers.json; writes data/arxiv_matches.json
# and data/<arxiv_id>/. Resume-safe at both phases. Polite 3s delay between hits.
import os, json, sys, time, re, io, gzip, tarfile
import urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
PAPERS = os.path.join(HERE, "data", "oral_papers.json")
OUT = os.path.join(HERE, "data", "arxiv_matches.json")
DATA = os.path.join(HERE, "data")
UA = "paper-buddy/1.0 (mailto:research@example.com)"  # swap real mailto if re-running
DELAY = 3.0
ATOM = "{http://www.w3.org/2005/Atom}"


def norm(s):
    # alphanumeric-only, lowercased, for strict equality
    return "".join(ch.lower() for ch in s if ch.isalnum())


def surnames(author_string):
    # ACL authors are comma-separated "First Last"; some entries trail a ';'.
    # Last whitespace token of each comma-split name is the surname.
    out = set()
    for name in author_string.replace(";", "").split(","):
        name = name.strip()
        if name:
            parts = name.split()
            if parts:
                out.add(parts[-1].lower())
    return out


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
    or_surnames = surnames(paper.get("authors", ""))
    if not or_surnames:
        return None
    for c in search_arxiv(or_title):
        if norm(or_title) == norm(c["title"]) and any(
            ax.split()[-1].lower() in or_surnames
            for ax in c["authors"] if ax.strip()
        ):
            return c["arxiv_id"]
    return None


def fetch(url, attempts=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for k in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError) as e:
            if k == attempts - 1:
                raise
            time.sleep(5 * (k + 1))


def save_eprint(arxiv_id, out_dir):
    data = fetch(f"https://arxiv.org/e-print/{arxiv_id}")
    os.makedirs(out_dir, exist_ok=True)
    try:
        raw = gzip.decompress(data)
    except OSError:
        raw = data
    if tarfile.is_tarfile(io.BytesIO(raw)):
        with tarfile.open(fileobj=io.BytesIO(raw)) as t:
            for m in t.getmembers():
                parts = [p for p in m.name.split("/") if p not in ("", ".")]
                if not parts:
                    continue
                tgt = os.path.join(out_dir, *parts)
                if not os.path.abspath(tgt).startswith(os.path.abspath(out_dir) + os.sep):
                    continue
                if m.isdir():
                    os.makedirs(tgt, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(tgt), exist_ok=True)
                    with t.extractfile(m) as src, open(tgt, "wb") as dst:
                        dst.write(src.read())
    else:
        with open(os.path.join(out_dir, "source"), "wb") as f:
            f.write(raw)


def has_tex(out_dir):
    if not os.path.isdir(out_dir):
        return False
    for _, _, files in os.walk(out_dir):
        if any(f.endswith(".tex") for f in files):
            return True
    return False


def main():
    papers = json.load(open(PAPERS))
    # ---- phase 1: match to arXiv (resume from arxiv_matches.json) ----
    existed = {}
    if os.path.exists(OUT):
        existed = {m["paper_number"]: m for m in json.load(open(OUT))}
    results = list(existed.values())
    done = set(existed.keys())
    todo = [p for p in papers if p["paper_number"] not in done]
    print(f"[match] {len(done)} decided, {len(todo)} to search", file=sys.stderr)
    for i, p in enumerate(todo, 1):
        aid = match_one(p)
        rec = {"paper_number": p["paper_number"], "title": p["title"],
               "authors": p["authors"], "arxiv_id": aid}
        results.append(rec)
        if aid:
            print(f"[{i}/{len(todo)}] OK   {p['paper_number']:10s} {p['title'][:50]:50s} -> {aid}",
                  file=sys.stderr)
        else:
            print(f"[{i}/{len(todo)}] MISS {p['paper_number']:10s} {p['title'][:50]:50s}",
                  file=sys.stderr)
        if i % 10 == 0:
            with open(OUT, "w") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
        time.sleep(DELAY)
    with open(OUT, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    matched = [r for r in results if r["arxiv_id"]]
    print(f"[match] {len(matched)}/{len(papers)} matched on arXiv", file=sys.stderr)

    # ---- phase 2: download LaTeX tarballs (resume by .tex presence) ----
    targets = matched
    print(f"[download] {len(targets)} tarballs to fetch", file=sys.stderr)
    ok, skip, err = 0, 0, 0
    for i, m in enumerate(targets, 1):
        aid = m["arxiv_id"]
        out_dir = os.path.join(DATA, aid)
        if has_tex(out_dir):
            skip += 1
            continue
        try:
            save_eprint(aid, out_dir)
            ok += 1
            print(f"[{i}/{len(targets)}] ok   {aid} ({m['title'][:45]})", file=sys.stderr)
        except Exception as e:
            err += 1
            print(f"[{i}/{len(targets)}] ERR  {aid}: {str(e)[:80]}", file=sys.stderr)
        time.sleep(DELAY)
    print(f"[download] downloaded={ok} skipped={skip} errors={err}", file=sys.stderr)
    print(f"[done] {len(matched)}/{len(papers)} matched, {ok} newly downloaded, "
          f"{skip} already present, {err} errors", file=sys.stderr)


if __name__ == "__main__":
    main()