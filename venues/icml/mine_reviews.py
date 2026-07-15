#!/usr/bin/env python3
# ponytail: mine recurring reviewer complaint patterns from 2068 ICML reviews.
# Output: data/review_patterns.json (stats) + skills/paper-critic/reference/
# review_patterns.md (human-readable).
# Review files are already anonymized on scrape (scrape_reviews.py stripped
# reviewer signatures); this script only needs to scan content fields.
import os, re, json, glob, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REVIEWS = os.path.join(HERE, "data", "reviews")
OUT_JSON = os.path.join(HERE, "data", "review_patterns.json")
OUT_MD = os.path.join(HERE, "skills", "paper-critic", "reference", "review_patterns.md")

# ponytail: parse the "weakness" sub-block out of the free-form
# strengths_and_weaknesses string. Reviewers delimit with a few common headers.
WEAK_SPLIT = re.compile(
    r"(?:\*{0,2}\s*(?:Weakness(?:es)?|W\b|Cons?|Limitations?|Concerns?|Issues?)\s*[:\*]+\s*)"
    r"|(?:\[\s*W\d?\s*\])"
    r"|(?:^|\n)\s*[-\u2022]\s*\*?\*?\s*W\b",
    re.I | re.M)
STRENGTH_SPLIT = re.compile(
    r"(?:\*{0,2}\s*(?:Strengths?|S\b|Pros?|Advantages?)\s*[:\*]+\s*)"
    r"|(?:\[\s*S\d?\s*\])",
    re.I | re.M)

# ponytail: reviewer-complaint pattern dictionary. Order matters — patterns are
# matched in order; first matching wins per sentence (so e.g. "missing ablation"
# counts as ablation not as missing-experiment). Each entry: (id, label, regex).
# Patterns are limited to the most common reviewer complaints observed in a
# manual scan of the first ~20 reviews; extended based on frequency.
PATTERNS = [
    ("baselines",
     "Weak / missing / outdated baselines",
     re.compile(r"\b(?:missing|weak|outdated|stronger|more|inadequate|limited|insufficient|lack\s+of|without)\s+(?:\w+\s+){0,2}baselines?\b"
               r"|\bbaselines?\s+(?:are|is)\s+(?:missing|weak|limited|insufficient|outdated|not\s+(?:strong|recent))",
               re.I)),
    ("ablation",
     "Missing / incomplete ablation study",
     re.compile(r"\b(?:missing|no|incomplete|insufficient|lack\s+of|without|more|additional)\s+(?:\w+\s+){0,2}ablation"
               r"|\bablation\s+(?:study|studies|is|are)\s+(?:missing|lacking|incomplete|not\s+(?:sufficient|provided))",
               re.I)),
    ("novelty",
     "Limited / incremental novelty",
     re.compile(r"\b(?:limited|incremental|not\s+(?:truly|sufficiently|very)|lack\s+of|insufficient|marginal|questionable|thin|not\s+novel|no\s+real)\s+(?:\w+\s+){0,2}novelty"
               r"|\bnot\s+(?:particularly\s+)?novel\b"
               r"|\bnovelty\s+is\s+(?:limited|questionable|thin|marginal)",
               re.I)),
    ("clarity",
     "Writing / clarity issues",
     re.compile(r"\b(?:unclear|hard\s+to\s+follow|confusing|hard\s+to\s+read|poorly\s+written|not\s+well\s+written|hard\s+to\s+understand|writing\s+is|clarity\s+(?:is|issues?))"
               r"|\bneeds?\s+(?:proofreading|editing|a\s+copy\s+edit|improvement\s+in\s+writing)",
               re.I)),
    ("experiments_scale",
     "Limited / insufficient experiments or scale",
     re.compile(r"\b(?:limited|insufficient|small-scale|limited\s+scale|more\s+experiments|additional\s+experiments|only\s+(?:a\s+)?(?:few|one|two)\s+(?:datasets|domains|tasks|experiments|settings)|lack\s+of\s+(?:large-scale|extensive)\s+experiments)"
               r"|\bexperiments\s+are\s+(?:limited|insufficient|inadequate)",
               re.I)),
    ("theory_analysis",
     "Missing theoretical / formal analysis",
     re.compile(r"\b(?:no|missing|lack\s+of|insufficient|incomplete|without|limited)\s+(?:\w+\s+){0,2}(?:theoretical|formal|mathematical)\s+(?:analysis|justification|proof|guarantee)"
               r"|\b(?!no\s+novelty)no\s+(?:theoretical\s+analysis|proof|theoretical\s+justification|guarantee)"
               r"|\b(?:theorem\s+is|proof\s+is)\s+(?:missing|incorrect|incomplete|not\s+provided)",
               re.I)),
    ("overclaim",
     "Overclaiming / unsupported claims",
     re.compile(r"\b(?:overclaim|over-?claim(?:ing|ed)?|exaggerat\w+|unsupported\s+claim|claim\s+is\s+not\s+supported|claims?\s+(?:are|is)\s+(?:too\s+)?strong|claims?\s+not\s+backed\s+by\s+(?:the\s+)?(?:experiments|evidence|results))",
               re.I)),
    ("motivation",
     "Unclear / weak motivation",
     re.compile(r"\b(?:unclear|weak|questionable|missing|lack\s+of)\s+(?:\w+\s+){0,2}motivation"
               r"|\bmotivation\s+(?:is|seems)\s+(?:unclear|weak|questionable|thin|missing)",
               re.I)),
    ("reproducibility",
     "Reproducibility / code missing",
     re.compile(r"\b(?:no|missing|lack\s+of|without)\s+(?:\w+\s+){0,2}(?:code|implementation|reproducibility)"
               r"|\bcosts?\s+of\s+reproduc\w+|\breproduc\w+\s+(?:is|issues?|concerns?)",
               re.I)),
    ("dataset_benchmark",
     "Limited / narrow datasets or benchmarks",
     re.compile(r"\b(?:limited|narrow|single|only\s+one|small)\s+(?:\w+\s+){0,2}(?:dataset|benchmark|testbed)s?\b"
               r"|\b(?:need|missing|additional|more)\s+(?:\w+\s+){0,2}(?:datasets|benchmarks)",
               re.I)),
    ("related_work",
     "Missing / incomplete related work or citations",
     re.compile(r"\b(?:missing|incomplete|lack\s+of|insufficient)\s+(?:\w+\s+){0,2}(?:related\s+work|citations?|references?)"
               r"|\brelated\s+work\s+is\s+(?:missing|incomplete|insufficient)",
               re.I)),
    ("soundness_error",
     "Technical / correctness errors",
     re.compile(r"\b(?:incorrect|wrong|bug|mistake|error\s+in|miscalculat|misstat\w+|technical\s+error|propositions?\s+is\s+incorrect|lemma\s+is\s+incorrect|proof\s+is\s+incorrect|equation\s+is\s+(?:incorrect|wrong))",
               re.I)),
    ("generalization",
     "Generalization / OOD / robustness concerns",
     re.compile(r"\b(?:lack\s+of|limited|concerns?\s+about|not\s+(?:clear|tested))\s+(?:\w+\s+){0,2}(?:generalization|generalizability|out-of-distribution|ood|robustness)"
               r"|\b(?:only|does\s+not)\s+(?:\w+\s+){0,2}(?:works?\s+on|tests?)\s+(?:a\s+|only\s+a\s+)?single\s+(?:dataset|domain|setting)",
               re.I)),
    ("efficiency_cost",
     "Compute / efficiency concerns",
     re.compile(r"\b(?:computational\s+cost|memory\s+cost|inference\s+cost|training\s+cost|efficiency\s+(?:concerns?|issues?))\s+(?:is|are)?\s*(?:high|too\s+high|prohibitive)?"
               r"|\bnot\s+(?:efficient|scalable|computationally\s+feasible)",
               re.I)),
    ("assumptions",
     "Restrictive / unrealistic assumptions",
     re.compile(r"\b(?:restrictive|unrealistic|strong|unreal)\s+assumptions?\s*(?:about|on)?|\bassumption\s+that\s+is\s+(?:strong|too\s+strong|restrictive|unrealistic)",
               re.I)),
]

# ponytail: extract sentence-like units (broad: also matches markdown bullet items).
SENT_RE = re.compile(r"[^.\n!?]{20,400}[.!?]|\n\s*[-\u2022\*]\s+[^\n]{15,300}", re.S)

def split_weakness_section(sw_text):
    """Return (weakness_text, full_text) — weakness_text is the part starting at
    the Weakness header; if no header found, returns the whole text (best effort)."""
    if not sw_text: return "", ""
    # Find the START of the weakness block.
    m = WEAK_SPLIT.search(sw_text)
    if not m:
        # no explicit weakness header -> treat the whole text as potential weakness
        # but also as strengths (we'll only flag negative patterns in weakness anyway)
        return sw_text, sw_text
    return sw_text[m.start():], sw_text

def sentences(text):
    if not text: return []
    out = []
    for m in SENT_RE.finditer(text):
        s = m.group(0).strip()
        # filter junk
        if 15 < len(s) < 400:
            # drop pure-line markers like "Strengths:", "**Weaknesses**"
            if not re.match(r"[*\s\-\u2022]*(?:Strengths?|Weakness(?:es)?|Cons?|Pros?|Issues?|Concerns?|Limitations?)\s*[:\*]*\s*$", s, re.I):
                out.append(s)
    return out

def clean_quote(s, max_len=180):
    # ponytail: make a verbatim safer to embed in markdown — strip markdown emphasis
    # markers that survive in our sentence matcher, collapse whitespace, truncate.
    q = re.sub(r"\*+", "", s)
    q = re.sub(r"\s+", " ", q).strip()
    if len(q) > max_len:
        # truncate to nearest whitespace before max_len
        q = q[:max_len].rsplit(" ", 1)[0] + "..."
    return q

def anonymize(s):
    # ponytail: strip email patterns, signal that name-with-author-ID isn't in our
    # scrape anyway; nothing further needed. Here for documentation — no-op.
    return s

def main():
    files = sorted(glob.glob(os.path.join(REVIEWS, "*.json")))
    if not files:
        print("[err] no reviews found in", REVIEWS, file=sys.stderr)
        sys.exit(1)
    reviews_data = []
    for f in files:
        try:
            d = json.load(open(f))
            reviews_data.append(d)
        except (OSError, json.JSONDecodeError):
            pass
    total_revs = sum(len(d.get("reviews", [])) for d in reviews_data)
    print(f"[load] {len(reviews_data)} papers, {total_revs} reviews",
          file=sys.stderr)

    # Count + sample
    pattern_count = Counter()  # pattern_id -> count of weakness-sentences matching
    pattern_examples = defaultdict(list)
    # Limit examples per pattern — store first 30, cull later.
    MAX_EXAMPLES_PER_PATTERN = 30

    skipped = 0
    for d in reviews_data:
        arxiv_id = None  # anonymized reference: paper_id not used in reference text
        paper_num = d.get("number")
        paper_title = d.get("title") or ""
        for r in d.get("reviews", []):
            sw = r.get("strengths_and_weaknesses") or ""
            lim = r.get("limitations") or ""
            # combine weaknesses
            weak_text, _ = split_weakness_section(sw)
            # only mine "weakness"-extracted text + limitations field; not strengths.
            weak_text = (weak_text or "") + "\n" + (lim or "")
            sens = sentences(weak_text)
            if not sens:
                skipped += 1
                continue
            matched_in_review = set()
            for sen in sens:
                for pid, label, pat in PATTERNS:
                    if pat.search(sen):
                        if pid not in matched_in_review:
                            # count once per review (avoid double-counting within the
                            # same review's multiple sentences mentioning same issue)
                            pattern_count[pid] += 1
                            matched_in_review.add(pid)
                        if len(pattern_examples[pid]) < MAX_EXAMPLES_PER_PATTERN:
                            pattern_examples[pid].append({
                                "snippet": anonymize(clean_quote(sen)),
                            })
                        break  # first-pattern-match wins per sentence
    print(f"[mine] {len(pattern_count)} unique patterns found; "
          f"{sum(pattern_count.values())} pattern instances across "
          f"{total_revs} reviews; {skipped} reviews had no parseable weakness text",
          file=sys.stderr)

    # build JSON
    out = {
        "n_papers": len(reviews_data),
        "n_reviews": total_revs,
        "n_reviews_without_weakness_text": skipped,
        "patterns": [
            {
                "id": pid,
                "label": label,
                "review_count": pattern_count[pid],
                "examples": pattern_examples[pid][:3],  # keep 3 in JSON for spot-checking
            }
            for (pid, label, _pat) in PATTERNS
            if pattern_count[pid] > 0
        ],
    }
    out["patterns"].sort(key=lambda p: -p["review_count"])
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=2)
    print(f"[done] wrote stats -> {OUT_JSON}", file=sys.stderr)

    # build markdown
    L = []
    L.append("# ICML 2026 — Reviewer Complaint Patterns (review-derived critic checklist)")
    L.append("")
    L.append(f"Aggregated by `mine_reviews.py` from **{out['n_reviews']} reviews** of "
             f"**{out['n_papers']} ICML spotlight papers**. (Skipped "
             f"{out['n_reviews_without_weakness_text']} reviews whose `strengths_and_weaknesses` "
             "had no parseable weakness text.) Reviewer identities were stripped at scrape "
             "time; snippets below are anonymized verbatim.")
    L.append("")
    L.append("## How to use this checklist")
    L.append("For each pattern below, the critic asks whether the **draft** exhibits the issue. "
             "Patterns are sorted from most to least common in the ICML review corpus — the top "
             "ones are what an ICML reviewer is most likely to raise. The `review_count` is the "
             "number of reviews (out of "
             f"{out['n_reviews']}; spotlight papers tend to receive 3-4 reviews each) where the "
             "weakness was detected — not all reviews touch every issue, so a count of e.g. 80 "
             "is already a very common complaint.")
    L.append("")
    L.append("Each pattern carries 1-3 anonymized verbatim snippets (drawn from the corresponding "
             "review sentences) so you can hear the actual reviewer voice. Apply each question to "
             "the draft's matching section; quote the draft where you can; do not paraphrase the "
             "issue inaccurately.")
    L.append("")
    L.append("## Reviewer complaint patterns (frequency-ranked)")
    L.append("")
    for i, p in enumerate(out["patterns"], 1):
        share = 100 * p["review_count"] / out["n_reviews"]
        L.append(f"### {i}. {p['label']}  (n={p['review_count']} reviews, "
                 f"{share:.0f}% of review corpus)")
        L.append("")
        # advisory question
        advisory = ADVISORY_QUESTIONS.get(p["id"], "")
        if advisory:
            L.append(f"**Critic question:** {advisory}")
            L.append("")
        examples = [e.get("snippet", "") for e in p.get("examples", [])][:2]
        if examples:
            L.append("**Reviewer examples (verbatim):**")
            for s in examples:
                L.append(f"- \"{s}\"")
            L.append("")
        else:
            L.append("_(no verbatim snippets kept at this frequency bucket)_\n")
    L.append("## Field-by-field meaning (for the runtime script)")
    L.append("`mine_reviews.py` reports these metrics; `inspect.py` may surface some during a "
             "draft scan when the matching pattern is detected in the draft text (lightweight "
             "match on cleaned section text):")
    L.append("")
    for pid, label, _pat in PATTERNS:
        c = pattern_count.get(pid, 0)
        L.append(f"- `{pid}` — {label} (review_corpus_count={c})")
    L.append("")
    L.append("_Generated by mine_reviews.py from data/reviews/*.json. Reviews were anonymized at "
             "scrape; only content fields and verbatim snippets appear here._")
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(L))
    print(f"[done] wrote review_patterns.md -> {OUT_MD}", file=sys.stderr)


# Ponytail: advisor-style question per pattern. Phrased as an open question for the
# critic skill to apply to the draft (not as a verdict on the draft).
ADVISORY_QUESTIONS = {
    "baselines": "Does the draft compare against the **most recent** and **strongest** baselines in its sub-field — not strawman or older methods that are easy to beat? Are there baselines from the last 12 months in the cited set?",
    "ablation": "If the draft makes contribution claims, is each one isolated by an ablation that **removes** that specific component while keeping the rest fixed? A paper with N contribution claims needs N ablations (one per claim).",
    "novelty": "Is the novelty claim something a reviewer can locate in the method — i.e. not 'we apply X to Y'? Incremental combinations are accepted when the combination itself is non-obvious; spell out why it is.",
    "clarity": "Would a grad student in an **adjacent** sub-area (not the author's own) follow the method section in one pass? Watch for undefined notation, jumps in the argument, and paragraphs that telegraph 'this will be clear to experts'.",
    "experiments_scale": "Does the experimental scope match the **scale of the claim**? A claim like 'our method works on diverse tasks' is unsupported by 1-2 tasks. Identify which tasks/datasets a reviewer would demand before accepting.",
    "theory_analysis": "If the draft makes a formal claim (convergence, sample complexity, optimality), is there a theorem/proof or pointer to one? If only an empirical claim, is the analysis still missing that a reviewer will want (e.g. why the method works)?",
    "overclaim": "For each superlative ('outperforms', 'state-of-the-art', 'first to'), can you point to a specific table/figure that backs it with numbers? If the claim is hedged ('competitive') is that a reframe of an SOTA claim that the experiments don't support?",
    "motivation": "Can a one-line answer to 'why is this paper needed?' be reconstructed from the intro? If the gap is implicit ('existing methods don't do X') does the draft cite the prior work that does X and what failed at the X attempt?",
    "reproducibility": "Are the experimental details (hyperparameters, seeds, hardware, dataset versions) sufficient for replication? Is a code URL promised? Camera-ready reproducibility is now scored at ICML; its complete absence costs the paper at review time.",
    "dataset_benchmark": "Does the draft evaluate on the standard benchmarks for its sub-field, or introduce a new one? If new, is there a justification for why the standard ones are insufficient (cherry-picking suspicion otherwise)?",
    "related_work": "Does the draft cite and differentiate the closest prior art? Are there missing references — large adjacent works a reviewer will know? Missing 1-2 obvious citations is a small flag; missing a body of work is a major flag.",
    "soundness_error": "Spot-check claims against the math/code. Are equations internally consistent? Are theorem statements correct? A single incorrect lemma can sink an otherwise-good paper; reviewers will look.",
    "generalization": "If the draft claims generalization (across datasets/domains/scales), is there direct evidence of it? OOD or domain-shift claims without OOD experiments are flagged immediately.",
    "efficiency_cost": "Does the draft report compute/memory/inference cost honestly? If the method trades quality for cost, is the trade-off numbers-on-the-table rather than vague? A reviewer will check if 'efficient' is benchmarked.",
    "assumptions": "Are the assumptions stated up front and defended? Strong / unrealistic assumptions are fine when acknowledged and their impact assessed; unstated assumptions invite reviewer skepticism.",
}


if __name__ == "__main__":
    main()