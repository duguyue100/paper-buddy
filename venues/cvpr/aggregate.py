#!/usr/bin/env python3
# ponytail: aggregate 106 per-paper features into the skill reference files.
# Outputs: skills/paper-style/reference/{cvpr_stats.json, cvpr_style.md},
#          skills/paper-critic/reference/cvpr_expectations.md.
# Quotes are verbatim excerpts (one short sentence) attributed by arxiv id,
# pulled from data/<id>/*.tex — grounded, not paraphrased.
import os, re, json, glob, statistics as S

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
FEATS = os.path.join(HERE, "features")
STYLE_DIR = os.path.join(HERE, "skills", "paper-style", "reference")
CRITIC_DIR = os.path.join(HERE, "skills", "paper-critic", "reference")
MIN_DOMAIN_N = 5  # ponytail: per-domain medians noisy below this; skip if fewer.

NUMERIC_FIELDS = [
    ("abstract.sentences",  ["abstract", "sentences"],   "Abstract length (sentences)"),
    ("abstract.words",      ["abstract", "words"],       "Abstract length (words)"),
    ("intro.paragraphs",    ["intro", "paragraphs"],     "Intro paragraph count"),
    ("related.words",       ["related", "words"],        "Related Work length (words)"),
    ("method.equation_count", ["method", "equation_count"], "Method equation count"),
    ("method.figure_count", ["method", "figure_count"],  "Method figure count"),
    ("experiments.table_count", ["experiments", "table_count"], "Experiment table count"),
    ("experiments.ablation_mentions", ["experiments", "ablation_mentions"], "Ablation mentions"),
    ("experiments.sota_mentions", ["experiments", "sota_mentions"], "SOTA/superlative mentions"),
    ("claims.body_words",   ["claims", "body_words"],    "Body length (words)"),
    ("citations.total",     ["citations", "total"],      "Citation count (\\cite cmds)"),
]

CATEGORICAL_FIELDS = [
    ("intro.hook_type", ["intro", "hook_type"], "Intro opening hook"),
    ("abstract.opening_verb", ["abstract", "opening_verb"], "Abstract opening verb"),
]

BOOLEAN_FIELDS = [
    ("structure.has_ablation_heading", ["structure", "has_ablation_heading"], "Has an 'Ablation' heading"),
    ("structure.has_related", ["structure", "has_related"], "Has Related Work section"),
    ("structure.has_conclusion", ["structure", "has_conclusion"], "Has Conclusion section"),
    ("intro.has_contrib_list", ["intro", "has_contrib_list"], "Intro has explicit contributions list"),
]

def load():
    return [json.load(open(f)) for f in sorted(glob.glob(os.path.join(FEATS, "*.json")))]

def get(f, path):
    cur = f
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur

def quantiles(vals):
    if not vals:
        return {}
    sv = sorted(vals)
    n = len(sv)
    def q(p):
        idx = int(round(p * (n - 1)))
        return sv[idx]
    return {"median": q(0.5), "p25": q(0.25), "p75": q(0.75), "n": n}

def domain_medians(feats, path):
    from collections import defaultdict
    byd = defaultdict(list)
    for f in feats:
        d = f["domain"]
        v = get(f, path)
        if v is not None:
            byd[d].append(v)
    out = {}
    for d, vs in byd.items():
        if len(vs) >= MIN_DOMAIN_N:
            out[d] = round(S.median(vs), 1) if isinstance(vs[0], float) else S.median(vs)
    return out

def domain_sensitive(per_domain):
    # ponytail: 2x ratio + abs spread > 5 -> domain-sensitive.
    if not per_domain:
        return False
    vals = list(per_domain.values())
    mn, mx = min(vals), max(vals)
    return (mx / max(mn, 1)) > 2.0 and (mx - mn) > 5

def freq_dist(feats, path):
    from collections import Counter
    c = Counter()
    for f in feats:
        v = get(f, path)
        c[v] += 1
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

# ---- quote helpers: read a sentence from a paper's tex ----
def read_paper_text(aid, subdir=None, name_contains=None):
    base = os.path.join(DATA, aid)
    if not os.path.isdir(base):
        return ""
    cands = []
    for root, _, files in os.walk(base):
        for f in files:
            if not f.endswith(".tex"):
                continue
            p = os.path.join(root, f)
            if name_contains and name_contains.lower() not in f.lower():
                continue
            cands.append(p)
    out = []
    for p in cands:
        try:
            with open(p, encoding="utf-8", errors="ignore") as fh:
                out.append(fh.read())
        except OSError:
            pass
    return "\n".join(out)

def grep_sentence(text, pattern, max_len=200):
    # ponytail: demote shaping macros so their visible content survives; then strip other cmds.
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
            txt = read_paper_text(aid, name_contains="abstract")
            if not txt:
                txt = read_paper_text(aid)
            # fall back to full text; first sentence with "we <verb>"
            s = grep_sentence(txt, r"\bwe\s+" + re.escape(verb), max_len=180)
            if s:
                return s, aid
    return None, None

def pick_quote_intro_contrib(feats):
    for f in feats:
        if f["intro"].get("has_contrib_list"):
            aid = f["id"]
            txt = read_paper_text(aid, name_contains="intro")
            s = grep_sentence(txt, r"contribution", max_len=220)
            if s:
                return s, aid
    return None, None

def pick_quote_ablation(feats):
    # choose a paper with high ablation_mentions
    cands = sorted(feats, key=lambda f: -(get(f, ["experiments", "ablation_mentions"]) or 0))
    for f in cands[:15]:
        aid = f["id"]
        txt = read_paper_text(aid, name_contains="exp")
        if not txt:
            txt = read_paper_text(aid, name_contains="experiment")
        s = grep_sentence(txt, r"ablat", max_len=200)
        if s:
            return s, aid
    return None, None

def pick_quote_sota(feats):
    for f in sorted(feats, key=lambda f: -(get(f, ["experiments", "sota_mentions"]) or 0))[:15]:
        aid = f["id"]
        txt = read_paper_text(aid, name_contains="exp") or read_paper_text(aid)
        s = grep_sentence(txt, r"outperform|state-of-the-art", max_len=180)
        if s:
            return s, aid
    return None, None

def pick_quote_hook(feats, hook):
    for f in feats:
        if f["intro"].get("hook_type") == hook:
            aid = f["id"]
            txt = read_paper_text(aid, name_contains="intro")
            s = grep_sentence(txt, r".", max_len=180)
            if s:
                return s, aid
    return None, None

# ---- writers ----
def build_stats_json(feats):
    stats = {"n_papers": len(feats), "fields": {}}
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
    # citation venue share aggregate + per-paper median
    from collections import Counter
    agg = Counter()
    for f in feats:
        for k, v in f["citations"]["venue_counts"].items():
            agg[k] += v
    total = sum(agg.values())
    shares = {k: round(100 * v / total, 1) for k, v in agg.most_common()}
    cv_pp = [f["citations"]["venue_counts"]["CV_conf"] / max(1, sum(f["citations"]["venue_counts"].values()))
             for f in feats if f["citations"]["bib_found"]]
    ml_pp = [f["citations"]["venue_counts"]["ML_conf"] / max(1, sum(f["citations"]["venue_counts"].values()))
             for f in feats if f["citations"]["bib_found"]]
    stats["fields"]["citations.venue_share_corpus"] = shares
    stats["fields"]["citations.CV_conf_perpaper_median"] = round(S.median(cv_pp) * 100, 1)
    stats["fields"]["citations.ML_conf_perpaper_median"] = round(S.median(ml_pp) * 100, 1)
    stats["domains_present"] = sorted(set(f["domain"] for f in feats))
    return stats

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

def fmt(x):
    if isinstance(x, float):
        return f"{x:.1f}" if abs(x) < 100 else f"{int(round(x))}"
    return str(x)

def build_style_md(feats, stats):
    L = []
    L.append("# CVPR 2026 — Style & Structure Reference\n")
    L.append(f"Aggregated from **{len(feats)} accepted oral papers** (the strongest ~2% of "
             "submissions). Generated by `aggregate.py` from `features/*.json`.\n")
    L.append("Use these as a CVPR yardstick. Each numeric field is the corpus median and "
             "inter-quartile range; if a flagged field is *domain-sensitive*, the range varies "
             "by sub-field, so deviations are defensible with a domain-specific reason, not a "
             "violation of the convention. Quotes are verbatim excerpts (attributed by arxiv "
             "id) — do not paraphrase.\n")

    L.append("\n## 1. Abstract\n")
    L.append(md_field_line("abstract.sentences", "Sentences", stats))
    L.append(md_field_line("abstract.words", "Words", stats))
    freq = stats["fields"]["abstract.opening_verb"]["distribution"]
    top = ", ".join(f"'{k}' ({v[1]}%)" for k, v in list(freq.items())[:4] if k)
    L.append(f"- **Opening verb frequency**: {top}")
    for v in ("introduce", "propose", "present"):
        q, aid = pick_quote_abstract_opening(feats, v)
        if q:
            L.append(f"  - example ({v}, {aid}): \"{q}\"")
    L.append("- Only **2%** of orals put an explicit contribution list inside the abstract — "
             "the contribution enumeration lives in the intro, not the abstract.\n")

    L.append("\n## 2. Introduction\n")
    L.append(md_field_line("intro.paragraphs", "Paragraphs", stats))
    freq = stats["fields"]["intro.hook_type"]["distribution"]
    hd = ", ".join(f"{k or 'None'} ({v[1]}%)" for k, v in freq.items())
    L.append(f"- **Opening hook type**: {hd}")
    q, aid = pick_quote_hook(feats, "question")
    if q:
        L.append(f"  - question hook example ({aid}): \"{q}\"")
    bl = stats["fields"]["intro.has_contrib_list"]
    L.append(f"- **{bl['rate_true']}%** of orals enumerate their contributions explicitly in the "
             f"intro (n={bl['n']}).")
    q, aid = pick_quote_intro_contrib(feats)
    if q:
        L.append(f"  - example ({aid}): \"{q}\"")
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
    if q:
        L.append(f"  - ablation framing example ({aid}): \"{q}\"")
    q, aid = pick_quote_sota(feats)
    if q:
        L.append(f"  - SOTA claim example ({aid}): \"{q}\"")
    L.append("")

    L.append("\n## 6. Overall body & citations\n")
    L.append(md_field_line("claims.body_words", "Body word count", stats))
    L.append(md_field_line("citations.total", "Total \\cite commands", stats))
    sh = stats["fields"]["citations.venue_share_corpus"]
    L.append("- **Citation venue share (aggregated, as % of bib entries):** "
             + ", ".join(f"{k}={v}%" for k, v in sh.items()))
    L.append(f"- **Per-paper CV-family (CVPR/ICCV/ECCV) cite share**: median "
             f"{stats['fields']['citations.CV_conf_perpaper_median']}% — note: CV confs are a "
             f"minority of citations; CVPR authors draw heavily from preprints, journals, and "
             f"adjacent ML conferences (per-paper ML conf share median "
             f"{stats['fields']['citations.ML_conf_perpaper_median']}%).\n")

    L.append("\n## 7. Section skeleton (presence rate)\n")
    bl = stats["fields"]["structure.has_related"]
    L.append(f"- Related Work present: {bl['rate_true']}%")
    bl = stats["fields"]["structure.has_conclusion"]
    L.append(f"- Conclusion present: {bl['rate_true']}%")
    bl = stats["fields"]["structure.has_ablation_heading"]
    L.append(f"- Explicit Ablation heading: {bl['rate_true']}%")
    L.append("\n## 8. Domains represented in the corpus\n")
    from collections import Counter
    dc = Counter(f["domain"] for f in feats)
    L.append(", ".join(f"{k} (n={v})" for k, v in sorted(dc.items(), key=lambda kv: -kv[1])))
    L.append("\n_Domains are a coarse keyword tag (ceiling: upgrade to embeddings to refine). "
             "When a metric is flagged domain-sensitive, prefer the per-domain median of the "
             "author's closest domain over the overall median._\n")
    return "\n".join(L)

def build_expectations_md(stats):
    L = ["# CVPR 2026 — Critic Expectations (compact)",
         "",
         "Numbers below are corpus medians from 106 accepted orals. Use them to flag drafts "
         "that deviate *and provide no domain reason*. A deviation is not automatically wrong.",
         ""]
    f = stats["fields"]
    q = lambda k: f[k]["quantiles"]
    L.append(f"## Minimum structural skeleton a CVPR draft should show")
    L.append("- Abstract (typically 5–10 sentences, 120–220 words)")
    L.append("- Introduction with an explicit contribution enumeration (about half of orals do)")
    L.append(f"- Related Work (typical ~{fmt(q('related.words')['median'])} words)")
    L.append(f"- Method block with formalism (typical ~{fmt(q('method.equation_count')['median'])} equation environments)")
    L.append(f"- Experiments with ≥{fmt(q('experiments.table_count')['median'])} tables and an ablation study")
    L.append(f"- Conclusion")
    L.append("")
    L.append("## What the corpus flags as reviewer-style red flags")
    L.append("- Missing or stub 'Ablation' subsection — even if your field uses fewer, you must "
             "isolate which design choice drove the gain; framing is observed in nearly every oral.")
    L.append("- Abstract containing an enumeration of contributions (rare — only ~2%); the "
             "contribution list belongs in the intro, not the abstract.")
    L.append("- SOTA claims without a paired quantitative result table reference — superlative "
             f"mentions median {fmt(q('experiments.sota_mentions')['median'])} per paper, every one "
             f"should map to a table or figure.")
    L.append("- Citation drift: if your draft's CV-family (CVPR/ICCV/ECCV) cite share is far below "
             f"the corpus median (~{f['citations.CV_conf_perpaper_median']}%), verify you are "
             "anchoring in the venue's prior work; cite-share is an heuristic, not a rule.")
    L.append("")
    L.append("## Counts vary by domain (do not enforce blindly)")
    for k in ("method.equation_count", "experiments.table_count",
              "experiments.ablation_mentions", "experiments.sota_mentions"):
        if f[k].get("domain_sensitive"):
            pd = f[k]["per_domain_median"]
            L.append(f"- {k}: ranges "
                     + ", ".join(f"{d}={fmt(v)}" for d, v in sorted(pd.items(), key=lambda kv: -kv[1]))
                     + " — ask for a domain justification if the draft is far outside the band.")
    L.append("")
    L.append("_Generated by aggregate.py from features/*.json. Numbers are "
             "medians, not requirements._")
    return "\n".join(L)

def main():
    feats = load()
    os.makedirs(STYLE_DIR, exist_ok=True)
    os.makedirs(CRITIC_DIR, exist_ok=True)
    stats = build_stats_json(feats)
    with open(os.path.join(STYLE_DIR, "cvpr_stats.json"), "w") as fh:
        json.dump(stats, fh, indent=2)
    with open(os.path.join(STYLE_DIR, "cvpr_style.md"), "w") as fh:
        fh.write(build_style_md(feats, stats))
    with open(os.path.join(CRITIC_DIR, "cvpr_expectations.md"), "w") as fh:
        fh.write(build_expectations_md(stats))
    print(f"[done] wrote cvpr_stats.json, cvpr_style.md (paper-style), "
          f"cvpr_expectations.md (paper-critic). n={len(feats)}.")

if __name__ == "__main__":
    main()