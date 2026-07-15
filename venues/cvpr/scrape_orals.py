#!/usr/bin/env python3
# ponytail: stdlib-only scraper for CVPR 2026 oral paper LaTeX sources.
# Pipeline: oral events page -> 141 oral detail pages -> openaccess paper html
# link -> arxiv abs url (mapped from the openaccess all-papers page) -> e-print
# tarball -> data/<arxiv_id>/.
import os, re, sys, time, tarfile, io, gzip, urllib.request, urllib.error

UA = "paper-buddy/1.0 (mailto:user@example.com)"  # ponytail: arxiv asks for contact
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DELAY = 3.0  # ponytail: polite delay between arxiv hits; tune down if trusted

def fetch(url, attempts=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for k in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            if k == attempts - 1:
                raise
            time.sleep(5 * (k + 1))

def build_arxiv_map():
    """Map /content/CVPR2026/html/.../paper.html -> arxiv abs url."""
    html = fetch("https://openaccess.thecvf.com/CVPR2026?day=all").decode("utf-8", "ignore")
    m = {}
    # each paper block: an anchor to paper.html then an arxiv abs anchor nearby.
    # ponytail: scan the whole doc in order, zip via regex alternation.
    pat = re.compile(
        r'href="(/content/CVPR2026/html/[^"]+)"|href="(https?://arxiv\.org/abs/[0-9.]{5,})"',
        re.I)
    last_html = None
    for a, b in pat.findall(html):
        if a:
            last_html = a
        elif b and last_html:
            m[last_html] = b
            last_html = None
    return m

def get_oral_detail_links():
    html = fetch("https://cvpr.thecvf.com/virtual/2026/events/Oral").decode("utf-8", "ignore")
    return sorted(set(re.findall(r'href="(/virtual/2026/oral/\d+)"', html)))

def extract_openaccess_link(detail_html):
    m = re.search(r'href="(https?://openaccess\.thecvf\.com/content/CVPR2026/html/[^"]+)"',
                  detail_html)
    if m:
        return m.group(1)
    m = re.search(r'/content/CVPR2026/html/[^"\s]+', detail_html)
    return m.group(0) if m else None

def extract_arxiv_id(abs_url):
    m = re.search(r'(\d{4}\.\d{4,5})', abs_url)
    return m.group(1) if m else None

def save_eprint(arxiv_id, out_dir):
    data = fetch(f"https://arxiv.org/e-print/{arxiv_id}")
    os.makedirs(out_dir, exist_ok=True)
    # ponytail: arxiv e-print is gzip; inner may be a tar or a single file.
    try:
        raw = gzip.decompress(data)
    except OSError:
        raw = data  # already raw tar/plain
    if tarfile.is_tarfile(io.BytesIO(raw)):
        with tarfile.open(fileobj=io.BytesIO(raw)) as t:
            for m in t.getmembers():
                # ponytail: zip-slip guard
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
        # single gzipped file (rare); dump as main.tex-ish.
        with open(os.path.join(out_dir, "source"), "wb") as f:
            f.write(raw)
    return True

def main():
    arxiv_map = build_arxiv_map()
    print(f"[map] {len(arxiv_map)} openaccess->arxiv entries", file=sys.stderr)
    orals = get_oral_detail_links()
    print(f"[oral] {len(orals)} oral papers", file=sys.stderr)
    ok = fail = 0
    for i, link in enumerate(orals, 1):
        full = "https://cvpr.thecvf.com" + link
        try:
            detail = fetch(full).decode("utf-8", "ignore")
        except Exception as e:
            print(f"[{i}/{len(orals)}] FAIL detail {link}: {e}", file=sys.stderr)
            fail += 1
            continue
        oa = extract_openaccess_link(detail)
        if not oa:
            print(f"[{i}/{len(orals)}] FAIL no openaccess link {link}", file=sys.stderr)
            fail += 1
            continue
        key = oa.split("thecvf.com")[-1] if "thecvf.com" in oa else oa
        abs_url = arxiv_map.get(key)
        if not abs_url:
            print(f"[{i}/{len(orals)}] FAIL no arxiv in map {key}", file=sys.stderr)
            fail += 1
            continue
        aid = extract_arxiv_id(abs_url)
        out_dir = os.path.join(DATA, aid)
        if os.path.isdir(out_dir):  # ponytail: skip if already downloaded, idempotent re-runs
            print(f"[{i}/{len(orals)}] skip existing {aid}", file=sys.stderr)
            ok += 1
            continue
        try:
            save_eprint(aid, out_dir)
            print(f"[{i}/{len(orals)}] ok {aid}", file=sys.stderr)
            ok += 1
        except Exception as e:
            print(f"[{i}/{len(orals)}] FAIL eprint {aid}: {e}", file=sys.stderr)
            fail += 1
        time.sleep(DELAY)
    print(f"[done] ok={ok} fail={fail}", file=sys.stderr)

if __name__ == "__main__":
    main()