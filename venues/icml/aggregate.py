#!/usr/bin/env python3
# ponytail: aggregate 303 per-paper features into the paper-style skill reference
# files. Outputs: skills/paper-style/reference/{icml_stats.json, icml_style.md},
#                skills/paper-critic/reference/icml_expectations.md.
# Quotes are verbatim excerpts (one short sentence) attributed by arxiv id,
# pulled from data/<id>/*.tex — grounded, not paraphrased.
# ICML delta vs CVPR aggregate: primary venue family is ML_conf (NeurIPS/ICLR/ICML)
# not CV_conf; per-paper MLfamily cite share is the new style-drift signal.
import os, re, json, glob, statistics as S
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
FEATS = os.path.join(HERE, "features")
STYLE_DIR = os.path.join(HERE, "skills", "paper-style", "reference")
CRITIC_DIR = os.path.join(HERE, "skills", "paper-critic", "reference")
MIN_DOMAIN_N = 5  # ponytail: per-domain medians noisy below this; skip if fewer.

NUMERIC_FIELDS = [
    ("abstract.sentences",          ["abstract", "sentences"],              "Abstract length (sentences)"),
    ("abstract.words",              ["abstract", "words"],                  "Abstract length (words)"),
    ("intro.paragraphs",            ["intro", "paragraphs"],                 "Intro paragraph count"),
    ("related.words",                ["related", "words"],                   "Related Work length (words)"),
    ("method.equation_count",       ["method", "equation_count"],            "Method equation count"),
    ("method.figure_count",         ["method", "figure_count"],              "Method figure count"),
    ("experiments.table_count",     ["experiments", "table_count"],          "Experiment table count"),
    ("experiments.ablation_mentions", ["experiments", "ablation_mentions"],   "Ablation mentions"),
    ("experiments.sota_mentions",   ["experiments", "sota_mentions"],       "SOTA/superlative mentions"),
    ("claims.body_words",           ["claims", "body_words"],                "Body length (words)"),
    ("citations.total",             ["citations", "total"],                 "Citation count (\\cite cmds)"),
]
CATEGORICAL_FIELDS = [
    ("intro.hook_type",      ["intro", "hook_type"],     "Intro opening hook"),
    ("abstract.opening_verb", ["abstract", "opening_verb"], "Abstract opening verb"),
]
BOOLEAN_FIELDS = [
    ("structure.has_ablation_heading", ["structure", "has_ablation_heading"], "Has an 'Ablation' heading"),
    ("structure.has_related",          ["structure", "has_related"],          "Has Related Work section"),
    ("structure.has_conclusion",       ["structure", "has_conclusion"],       "Has Conclusion section"),
    ("intro.has_contrib_list",          ["intro", "has_contrib_list"],         "Intro has explicit contributions list"),
]

def load():
    return [json.load(open(f)) for f in sorted(glob.glob(os.path.join(FEATS, "*.json")))
            if not json.load(open(f)).get("error")]

def get(f, path):
    cur = f
    for k in path:
        if not isinstance(cur, dict) or k not in cur: return None
        cur = cur[k]
    return cur

def quantiles(vals):
    if not vals: return {}
    sv = sorted(vals); n = len(sv)
    def q(p): return sv[int(round(p * (n - 1)))]
    return {"median": q(0.5), "p25": q(0.25), "p75": q(0.75), "n": n}

def domain_medians(feats, path):
    byd = {}
    for f in feats:
        d = f.get("domain")
        v = get(f, path)
        if v is not None and d is not None:
            byd.setdefault(d, []).append(v)
    out = {}
    for d, vs in byd.items():
        if len(vs) >= MIN_DOMAIN_N:
            out[d] = round(S.median(vs), 1) if isinstance(vs[0], float) else S.median(vs)
    return out

def domain_sensitive(per_domain):
    if not per_domain: return False
    vals = list(per_domain.values())
    mn, mx = min(vals), max(vals)
    return (mx / max(mn, 1)) > 2.0 and (mx - mn) > 5

def freq_dist(feats, path):
    c = Counter()
    for f in feats:
        v = get(f, path); c[v] += 1
    total = sum(c.values())
    return {k: (v, round(100 * v / total, 1)) for k, v in c.most_common()}

def bool_rate(feats, path):
    n_t = n_f = 0
    for f in feats:
        v = get(f, path)
        if v is True: n_t += 1
        elif v is False: n_f += 1
    total = n_t + n_f
    return {"true": n_t, "false": n_f, "rate_true": round(100 * n_t / total, 1) if total else 0, "n": total}

def read_paper_text(aid, name_contains=None):
    base = os.path.join(DATA, aid)
    if not os.path.isdir(base): return ""
    cands = []
    for root, _, files in os.walk(base):
        for f in files:
            if not f.endswith(".tex"): continue
            p = os.path.join(root, f)
            if name_contains and name_contains.lower() not in f.lower(): continue
            cands.append(p)
    out = []
    for p in cands:
        try:
            with open(p, encoding="utf-8", errors="ignore") as fh: out.append(fh.read())
        except OSError: pass
    return "\n".join(out)

def grep_sentence(text, pattern, max_len=200):
    blob = re.sub(r"\\(textbf|emph|textit|texttt|text|mathbf|mathrm|mathit|bf|it|tt|"
                  r"bfseries|itshape|underline|textrm|textsf)\b\s*\{", "{", text)
    blob = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})*", " ", blob)
    blob = re.sub(r"[{}\\]", "", blob)
    blob = re.sub(r"~", " ", blob)
    blob = re.sub(r"\[\s*\]", " ", blob)
    blob = re.sub(r"\s+([.,;:!?])", r"\1", blob)
    blob = re.sub(r"\s+", " ", blob)
    for m in re.finditer(r"[^.!?\n]{15," + str(max_len) + r"}[.!?]", blob):
        s = m.group(0).strip()
        if re.search(pattern, s, re.I) and len(s) < max_len:
            return s
    return None

def pick_quote_abstract_opening(feats, verb):
    for f in feats:
        if f["abstract"].get("opening_verb") == verb:
            aid = f["id"]
            txt = read_paper_text(aid, name_contains="abstract") or read_paper_text(aid)
            s = grep_sentence(txt, r"\bwe\s+" + re.escape(verb), max_len=180)
            if s: return s, aid
    return None, None

def pick_quote_intro_contrib(feats):
    for f in feats:
        if f["intro"].get("has_contrib_list"):
            aid = f["id"]
            txt = read_paper_text(aid, name_contains="intro")
            s = grep_sentence(txt, r"contribution", max_len=220)
            if s: return s, aid
    return None, None

def pick_quote_ablation(feats):
    cands = sorted(feats, key=lambda f: -(get(f, ["experiments", "ablation_mentions"]) or 0))
    for f in cands[:15]:
        aid = f["id"]
        txt = read_paper_text(aid, name_contains="exp") or read_paper_text(aid, name_contains="experiment")
        s = grep_sentence(txt, r"ablat", max_len=200)
        if s: return s, aid
    return None, None

def pick_quote_sota(feats):
    for f in sorted(feats, key=lambda f: -(get(f, ["experiments", "sota_mentions"]) or 0))[:15]:
        aid = f["id"]
        txt = read_paper_text(aid, name_contains="exp") or read_paper_text(aid)
        s = grep_sentence(txt, r"outperform|state-of-the-art", max_len=180)
        if s: return s, aid
    return None, None

def pick_quote_hook(feats, hook):
    for f in feats:
        if f["intro"].get("hook_type") == hook:
            aid = f["id"]
            txt = read_paper_text(aid, name_contains="intro")
            s = grep_sentence(txt, r".", max_len=180)
            if s: return s, aid
    return None, None

def build_stats_json(feats):
    stats = {"n_papers": len(feats), "venue": "ICML 2026 spotlight", "fields": {}}
    for key, path, _ in NUMERIC_FIELDS:
        vals = [v for v in (get(f, path) for f in feats) if v is not None]
        pd = domain_medians(feats, path)
        stats["fields"][key] = {
            "quantiles": quantiles(vals),
            "per_domain_median": pd,
            "domain_sensitive": domain_sensitive(pd),
        }
    for key, path, _ in CATEGORICAL_FIELDS:
        stats["fields"][key] = {"distribution": freq_dist(feats, path)}
    for key, path, _ in BOOLEAN_FIELDS:
        stats["fields"][key] = bool_rate(feats, path)
    agg = Counter()
    for f in feats:
        for k, v in f["citations"]["venue_counts"].items():
            agg[k] += v
    total = sum(agg.values())
    shares = {k: round(100 * v / total, 1) for k, v in agg.most_common()}
    ml_pp = [f["citations"]["venue_counts"]["ML_conf"] / max(1, sum(f["citations"]["venue_counts"].values()))
             for f in feats if f["citations"]["bib_found"]]
    cv_pp = [f["citations"]["venue_counts"]["CV_conf"] / max(1, sum(f["citations"]["venue_counts"].values()))
             for f in feats if f["citations"]["bib_found"]]
    stats["fields"]["citations.venue_share_corpus"] = shares
    stats["fields"]["citations.ML_conf_perpaper_median"] = round(S.median(ml_pp) * 100, 1)
    stats["fields"]["citations.CV_conf_perpaper_median"] = round(S.median(cv_pp) * 100, 1)
    stats["domains_present"] = sorted(set(f["domain"] for f in feats))
    return stats

def fmt(x):
    if isinstance(x, float): return f"{x:.1f}" if abs(x) < 100 else f"{int(round(x))}"
    return str(x)

def md_field_line(name, label, stats):
    fs = stats["fields"][name]
    q = fs["quantiles"]
    dom = fs.get("per_domain_median", {})
    sens = fs.get("domain_sensitive")
    line = (f"- **{label}**: median={fmt(q['median'])} "
            f"(P25={fmt(q['p25'])}, P75={fmt(q['p75'])}, n={q['n']})")
    if dom:
        dline = "; ".join(f"{k}={fmt(v)}" for k, v in sorted(dom.items(), key=lambda kv: -kv[1]))
        line += f"\n  - per-domain median: {dline}"
    if sens:
        line += "\n  - **domain-sensitive** — justify your deviation by domain"
    return line

def build_style_md(feats, stats):
    L = []
    L.append("# ICML 2026 — Style & Structure Reference\n")
    L.append(f"Aggregated from **{len(feats)} accepted spotlight papers** with arXiv LaTeX "
             "sources. Generated by `aggregate.py` from `features/*.json`. "
             "(OpenReview's 2026 spotlight list has 536 papers; 303 were matched on "
             "arXiv by title-and-author surname — see `match_arxiv.py`.)\n")
    L.append("Use these as an ICML yardstick. Each numeric field is the corpus median and "
             "inter-quartile range; if a flagged field is *domain-sensitive*, the range varies "
             "by sub-field, so deviations are defensible with a domain-specific reason, not a "
             "violation of the convention. Quotes are verbatim excerpts (attributed by arxiv "
             "id) — do not paraphrase.\n")
    L.append("Domain tags come from OpenReview's `primary_area` field, normalized to 10 buckets "
             "(see `extract.py`); for drafts without an OpenReview area, a keyword classifier "
             "matching the same 10 buckets is used.\n")

    L.append("\n## 1. Abstract\n")
    L.append(md_field_line("abstract.sentences", "Sentences", stats))
    L.append(md_field_line("abstract.words", "Words", stats))
    freq = stats["fields"]["abstract.opening_verb"]["distribution"]
    top = ", ".join(f"'{k}' ({v[1]}%)" for k, v in list(freq.items())[:4] if k)
    L.append(f"- **Opening verb frequency**: {top}")
    for v in ("introduce", "propose", "present"):
        q, aid = pick_quote_abstract_opening(feats, v)
        if q: L.append(f"  - example ({v}, {aid}): \"{q}\"")
    bl = stats["fields"]["intro.has_contrib_list"]
    # ponytail: count abstract contrib list separately
    abs_contrib_pct = round(100 * sum(1 for f in feats if f["abstract"].get("has_contrib_list")) / len(feats), 1)
    L.append(f"- Only **{abs_contrib_pct}%** of spotlights put an explicit contribution list "
             "inside the abstract — the contribution enumeration lives in the intro, not the abstract.\n")

    L.append("\n## 2. Introduction\n")
    L.append(md_field_line("intro.paragraphs", "Paragraphs", stats))
    freq = stats["fields"]["intro.hook_type"]["distribution"]
    hd = ", ".join(f"{k or 'None'} ({v[1]}%)" for k, v in freq.items())
    L.append(f"- **Opening hook type**: {hd}")
    q, aid = pick_quote_hook(feats, "question")
    if q: L.append(f"  - question hook example ({aid}): \"{q}\"")
    bl = stats["fields"]["intro.has_contrib_list"]
    L.append(f"- **{bl['rate_true']}%** of spotlights enumerate their contributions explicitly in "
             f"the intro (n={bl['n']}).")
    q, aid = pick_quote_intro_contrib(feats)
    if q: L.append(f"  - example ({aid}): \"{q}\"")
    L.append("")

    L.append("\n## 3. Related Work\n")
    L.append(md_field_line("related.words", "Word count", stats))
    bl = stats["fields"]["structure.has_related"]
    L.append(f"- **{bl['rate_true']}%** include a Related Work heading.\n")

    L.append("\n## 4. Method\n")
    L.append(md_field_line("method.equation_count", "Equation environments", stats))
    L.append(md_field_line("method.figure_count", "Figures inside the method block", stats))

    L.append("\n## 5. Experiments\n")
    L.append(md_field_line("experiments.table_count", "Tables", stats))
    L.append(md_field_line("experiments.ablation_mentions", "Ablation mentions", stats))
    L.append(md_field_line("experiments.sota_mentions", "SOTA/outperform mentions", stats))
    bl = stats["fields"]["structure.has_ablation_heading"]
    L.append(f"- **{bl['rate_true']}%** have an explicit 'Ablation' (sub)section heading.")
    q, aid = pick_quote_ablation(feats)
    if q: L.append(f"  - ablation framing example ({aid}): \"{q}\"")
    q, aid = pick_quote_sota(feats)
    if q: L.append(f"  - SOTA claim example ({aid}): \"{q}\"")
    L.append("")

    L.append("\n## 6. Overall body & citations\n")
    L.append(md_field_line("claims.body_words", "Body word count", stats))
    L.append(md_field_line("citations.total", "Total \\cite commands", stats))
    sh = stats["fields"]["citations.venue_share_corpus"]
    L.append("- **Citation venue share (aggregated, as % of bib entries):** "
             + ", ".join(f"{k}={v}%" for k, v in sh.items()))
    L.append(f"- **Per-paper ML-family (NeurIPS/ICML/ICLR/COLT/AISTATS/etc.) cite share**: median "
             f"{stats['fields']['citations.ML_conf_perpaper_median']}% — ICML authors anchor "
             f"heavily in the ML conference family; preprints are also major (per-paper CV "
             f"conf share median {stats['fields']['citations.CV_conf_perpaper_median']}%, "
             "lower as ICML is broader than vision).\n")

    L.append("\n## 7. Section skeleton (presence rate)\n")
    bl = stats["fields"]["structure.has_related"]
    L.append(f"- Related Work present: {bl['rate_true']}%")
    bl = stats["fields"]["structure.has_conclusion"]
    L.append(f"- Conclusion present: {bl['rate_true']}%")
    bl = stats["fields"]["structure.has_ablation_heading"]
    L.append(f"- Explicit Ablation heading: {bl['rate_true']}%")

    L.append("\n## 8. Domains represented in the corpus\n")
    dc = Counter(f["domain"] for f in feats)
    L.append(", ".join(f"{k} (n={v})" for k, v in sorted(dc.items(), key=lambda kv: -kv[1])))
    L.append("\n_Domains are normalized from OpenReview's `primary_area` field to 10 buckets "
             "(see `extract.py`). When a metric is flagged domain-sensitive, prefer the "
             "per-domain median of the author's closest domain over the overall median._\n")
    return "\n".join(L)

def build_expectations_md(stats):
    L = ["# ICML 2026 — Critic Expectations (compact)",
         "",
         f"Numbers below are corpus medians from {stats['n_papers']} accepted spotlights with "
         "arXiv sources. Use them to flag drafts that deviate *and provide no domain reason*. "
         "A deviation is not automatically wrong.",
         ""]
    f = stats["fields"]
    q = lambda k: f[k]["quantiles"]
    L.append("## Minimum structural skeleton an ICML draft should show")
    L.append(f"- Abstract (typically {fmt(q('abstract.sentences')['median'])}-{fmt(q('abstract.sentences')['p75'])} "
             f"sentences, {fmt(q('abstract.words')['median'])}-{fmt(q('abstract.words')['p75'])} words)")
    L.append("- Introduction with an explicit contribution enumeration "
             f"({stats['fields']['intro.has_contrib_list']['rate_true']}% of spotlights do)")
    L.append(f"- Related Work (typical ~{fmt(q('related.words')['median'])} words)")
    L.append(f"- Method block with formalism (typical ~{fmt(q('method.equation_count')['median'])} equation environments — "
             "ICML is theory-heavy)")
    L.append(f"- Experiments with ≥{fmt(q('experiments.table_count')['median'])} tables and an ablation study")
    L.append("- Conclusion")
    L.append("")
    L.append("## What the corpus flags as reviewer-style red flags")
    L.append(f"- Missing or stub 'Ablation' subsection — {stats['fields']['structure.has_ablation_heading']['rate_true']}% "
             "of spotlights have an explicit Ablation heading; a missing one will be flagged.")
    L.append(f"- Abstract containing an enumeration of contributions (rare in ICML); the "
             "contribution list belongs in the intro, not the abstract.")
    L.append("- SOTA claims without a paired quantitative result table reference — superlative "
             f"mentions median {fmt(q('experiments.sota_mentions')['median'])} per paper, every one "
             "should map to a table or figure (the `inspect.py` script flags unanchored superlatives directly).")
    L.append("- Citation drift: if your draft's ML-family (NeurIPS/ICML/ICLR/COLT/AISTATS/AAAI..."
             f") cite share is far below the corpus per-paper median "
             f"(~{f['citations.ML_conf_perpaper_median']}%), verify you are anchoring in the "
             "ML community's prior work. (ICML authors draw broadly — preprints take a large share "
             f"too; the CV-family share median {f['citations.CV_conf_perpaper_median']}% is naturally "
             "lower for ICML than for a CVPR paper.)")
    L.append("")
    L.append("## Numbers vary by domain (do not enforce blindly)")
    L.append("The critic must ASK for a domain reason when the draft's value is outside the band below.")
    for k in ("method.equation_count", "experiments.table_count",
              "experiments.ablation_mentions", "experiments.sota_mentions",
              "citations.total", "related.words"):
        if f[k].get("domain_sensitive"):
            pd = f[k]["per_domain_median"]
            L.append(f"- {k}: ranges "
                     + ", ".join(f"{d}={fmt(v)}" for d, v in sorted(pd.items(), key=lambda kv: -kv[1]))
                     + " — ask for a domain justification if the draft is far outside the band.")
    L.append("")
    L.append("## Review-derived patterns (priority reviewer complaints)")
    L.append("For the prose-style review-derived checklist (frequency-ranked reviewer complaint "
             "patterns + verbatim reviewer examples + domain-neutral advisory questions for each), "
             "see `review_patterns.md` in this folder. That file is generated by `mine_reviews.py` "
             "from the 2068 OpenReview reviews of all 536 ICML 2026 spotlight papers.")
    L.append("")
    L.append("_Generated by aggregate.py from features/*.json. Numbers are medians, not requirements._")
    return "\n".join(L)

def main():
    feats = load()
    if not feats:
        print("[err] no features found in", FEATS, file=sys.stderr)
        return
    os.makedirs(STYLE_DIR, exist_ok=True)
    os.makedirs(CRITIC_DIR, exist_ok=True)
    stats = build_stats_json(feats)
    with open(os.path.join(STYLE_DIR, "icml_stats.json"), "w") as fh:
        json.dump(stats, fh, indent=2)
    with open(os.path.join(STYLE_DIR, "icml_style.md"), "w") as fh:
        fh.write(build_style_md(feats, stats))
    with open(os.path.join(CRITIC_DIR, "icml_expectations.md"), "w") as fh:
        fh.write(build_expectations_md(stats))
    print(f"[done] wrote icml_stats.json, icml_style.md (paper-style), "
          f"icml_expectations.md (paper-critic). n={len(feats)}.")

if __name__ == "__main__":
    main()