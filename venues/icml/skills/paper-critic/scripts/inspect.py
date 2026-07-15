#!/usr/bin/env python3
# ponytail: runtime draft inspector for the ICML paper-critic skill.
# Extracts section text + structural critique signals from a draft so the
# model can apply review_patterns.md (ICML review-derived checklist) and
# icml_expectations.md (corpus medians) deterministically.
# New ICML capability: scans draft section text for matches against the same
# complaint patterns mined from ICML reviews (loaded from review_patterns.json)
# so the critic can flag e.g. "weak baselines" wording in the draft itself.
# Usage: python inspect.py <draft.tex or dir> [section_name_substring]
import os, sys, re, json

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_EXTRACT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "extract.py"))
REPO_MINE = os.path.abspath(os.path.join(HERE, "..", "..", "..", "mine_reviews.py"))
sys.path.insert(0, os.path.dirname(REPO_EXTRACT))
import extract  # noqa: E402

# ponytail: load the review-pattern dictionary at runtime to scan the draft with.
PATTERNS_JSON = os.path.join(HERE, "..", "..", "..", "data", "review_patterns.json")

SUPERL = re.compile(r"\b(state-of-the-art|SOTA|outperform|novel|first to|best|superior|surpass)\b", re.I)
REF_RE = re.compile(r"\\(?:ref|cref|autoref|eqref)\b\s*\{[^}]*\}")
HEDGE = re.compile(r"\b(can|may|might|could|typically|usually|often|in general|tends to)\b", re.I)
CONTRIB_RE = re.compile(r"(our|the)\s+(key\s+|main\s+)?contributions?\s+(are|is|include|summariz)", re.I)
ABLATION_RE = re.compile(r"ablation", re.I)

def clean_for_read(text, max_chars=3500):
    blob = re.sub(r"\\(textbf|emph|textit|texttt|text|mathbf|mathrm|mathit|bf|it|tt|"
                  r"bfseries|itshape|underline|textrm|textsf)\b\s*\{", "{", text)
    blob = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})*", " ", blob)
    blob = re.sub(r"[{}\\~]", "", blob)
    blob = re.sub(r"\s+([.,;:!?])", r"\1", blob)
    blob = re.sub(r"\s+", " ", blob).strip()
    return blob[:max_chars]

def signals_for_section(sec_text):
    sup = SUPERL.findall(sec_text)
    refs = REF_RE.findall(sec_text)
    hed = HEDGE.findall(sec_text)
    unanchored = 0
    for m in SUPERL.finditer(sec_text):
        window = sec_text[max(0, m.start()-200):m.end()+200]
        if not REF_RE.search(window):
            unanchored += 1
    return {
        "superlative_mentions": len(sup),
        "superlatives_with_no_nearby_ref": unanchored,
        "ref_commands": len(refs),
        "hedging_words": len(hed),
        "has_contrib_list": bool(CONTRIB_RE.search(sec_text)),
        "ablation_mentions": len(ABLATION_RE.findall(sec_text)),
        "word_count": extract.count_words(sec_text),
    }

def load_review_patterns():
    # ponytail: load review_patterns.json produced by mine_reviews.py.
    # Each entry has {id, label, regex-pattern compiled at mine-time}.
    # We rebuild the regexes from the source via the import path (no, simpler:
    # we just store the pattern id and re.compile the same dict by re-importing
    # patterns from mine_reviews.py's PATTERNS list.)
    if not os.path.exists(PATTERNS_JSON):
        return []
    sys.path.insert(0, os.path.dirname(REPO_MINE))
    import mine_reviews as mr  # noqa: E402
    data = json.load(open(PATTERNS_JSON))
    by_id = {p["id"]: p for p in data.get("patterns", [])}
    return [(pid, by_id[pid]["label"], pat) for (pid, label, pat) in mr.PATTERNS if pid in by_id]

def scan_review_patterns(text):
    # ponytail: returns list of (pattern_id, label, matched_substring) found in text.
    out = []
    cleaned = clean_for_read(text, max_chars=10000)
    for pid, label, pat in load_review_patterns():
        m = pat.search(cleaned)
        if m:
            snip = m.group(0)
            # trim to ~80 chars for display
            if len(snip) > 80:
                snip = snip[:80].rsplit(" ", 1)[0] + "..."
            out.append((pid, label, snip))
    return out

def pick_section(body, sections, spans, want):
    if not sections: return None, "", -1
    want = want.lower()
    for i, s in enumerate(sections):
        if want in s.lower():
            a, b = spans[i]
            return s, body[a:b], i
    return None, "", -1

def main():
    if len(sys.argv) < 2:
        print("usage: inspect.py <draft.tex or dir> [section_substring]", file=sys.stderr)
        sys.exit(2)
    target = sys.argv[1]
    paper_dir = target if os.path.isdir(target) else (os.path.dirname(os.path.abspath(target)) or ".")
    want = sys.argv[2] if len(sys.argv) > 2 else None

    root = extract.find_root_tex(paper_dir)
    if not root:
        print("ERROR: no tex with \\documentclass found", file=sys.stderr)
        sys.exit(1)
    full = extract.resolve_inputs(root, paper_dir)
    nc = extract.strip_comments(full)
    body = extract.get_body(nc)

    abs_text = extract.extract_abstract_with_fallback(nc, paper_dir) or ""
    sections = extract.SECTION_TITLES_RE.findall(body)
    spans = extract.section_spans(body, sections)

    print(f"# Draft inspection: {os.path.basename(os.path.abspath(paper_dir))}")
    print(f"root tex: {os.path.relpath(root, paper_dir)}")
    print(f"sections detected: {len(sections)}")
    for s in sections:
        print(f"  - {s}")
    print()

    blocks = []
    if want:
        title, txt, idx = pick_section(body, sections, spans, want)
        if title is None:
            print(f"## Requested section '{want}' NOT FOUND. Available sections listed above.")
            sys.exit(0)
        blocks.append((title, txt))
    else:
        for want_key in ("intro", "experiment", "result", "evaluat"):
            title, txt, idx = pick_section(body, sections, spans, want_key)
            if title and any(t == title for t, _ in blocks):
                continue
            if title:
                blocks.append((title, txt))
        if abs_text:
            blocks.append(("Abstract", abs_text))
        abl_idx = None
        for i, s in enumerate(sections):
            if ABLATION_RE.search(s):
                abl_idx = i; break
        if abl_idx is not None:
            a, b = spans[abl_idx]
            blocks.append((sections[abl_idx], body[a:b]))

    print("## Section critiques")
    for title, txt in blocks:
        print(f"\n### {title}")
        sig = signals_for_section(txt)
        print(f"  words={sig['word_count']}, superlatives={sig['superlative_mentions']} "
              f"(unanchored={sig['superlatives_with_no_nearby_ref']}), refs={sig['ref_commands']}, "
              f"hedging={sig['hedging_words']}, ablation_mentions={sig['ablation_mentions']}, "
              f"has_contrib_list={sig['has_contrib_list']}")
        if sig["superlatives_with_no_nearby_ref"] > 0:
            print(f"  [RED FLAG] {sig['superlatives_with_no_nearby_ref']} superlative(s) with no "
                  f"\\ref within 200 chars — each SOTA claim should anchor to a table/figure.")
        if sig["superlative_mentions"] > 3 and sig["hedging_words"] == 0:
            print("  [NOTE] many superlatives, zero hedging — verify the claim-to-evidence ratio.")
        # ponytail: review-pattern scan
        rp = scan_review_patterns(txt)
        if rp:
            print(f"  [REVIEW-PATTERN MATCHES] (from ICML review corpus):")
            for pid, label, snip in rp[:5]:
                print(f"    - {pid}: {label} | draft: \"{snip}\"")
        print("  [TEXT FOR REVIEW] " + clean_for_read(txt, 2500))

    # global missing-section flags
    print("\n## Structural completeness (vs ICML expectations)")
    role_intro = extract.find_role_idx(sections, extract.ROLE_INTRO_RE)
    role_rel = extract.find_role_idx(sections, extract.ROLE_RELATED_RE)
    role_exp = extract.find_role_idx(sections, extract.ROLE_EXP_RE)
    role_concl = extract.find_role_idx(sections, extract.ROLE_CONCL_RE)
    abl = any(ABLATION_RE.search(s) for s in sections)
    for label, ok in [("Intro", role_intro is not None),
                      ("Related Work", role_rel is not None),
                      ("Experiments", role_exp is not None),
                      ("Conclusion", role_concl is not None),
                      ("Ablation heading", abl),
                      ("Abstract", bool(abs_text))]:
        print(f"  {'OK ' if ok else 'MISSING'} {label}")

if __name__ == "__main__":
    main()