#!/usr/bin/env python3
# ponytail: download arXiv e-print tarballs for ICML 2026 spotlight papers that
# matched in match_arxiv.py. Saves to data/<arxiv_id>/. Resume-safe: skips
# already-downloaded ids (any .tex file present).
import os, json, sys, time, tarfile, io, gzip
import urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
MATCHES = os.path.join(HERE, "data", "arxiv_matches.json")
DATA = os.path.join(HERE, "data")
UA = "paper-buddy/1.0 (mailto:research@example.com)"  # swap real mailto if re-running
DELAY = 3.0


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
    return any(f.endswith(".tex") for f in os.listdir(out_dir)) if os.path.isdir(out_dir) else False


def main():
    matches = json.load(open(MATCHES))
    targets = [m for m in matches if m.get("arxiv_id")]
    print(f"[plan] {len(targets)} arxiv tarballs to download", file=sys.stderr)
    ok, skip, err = 0, 0, 0
    for i, m in enumerate(targets, 1):
        aid = m["arxiv_id"]
        out_dir = os.path.join(DATA, aid)
        if has_tex(out_dir):
            skip += 1
            if i % 50 == 0:
                print(f"[{i}/{len(targets)}] skip {aid} (exists)", file=sys.stderr)
            continue
        try:
            save_eprint(aid, out_dir)
            ok += 1
            print(f"[{i}/{len(targets)}] ok   {aid} ({m['title'][:45]})",
                  file=sys.stderr)
        except Exception as e:
            err += 1
            print(f"[{i}/{len(targets)}] ERR  {aid}: {str(e)[:80]}",
                  file=sys.stderr)
        time.sleep(DELAY)
    print(f"[done] downloaded={ok} skipped={skip} errors={err}",
          file=sys.stderr)


if __name__ == "__main__":
    main()