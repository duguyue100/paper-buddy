#!/usr/bin/env python3
# ponytail: runtime style analyzer for the ICML paper-style skill.
# Measures a draft with the SAME extractor core as the ICML corpus, compares to
# icml_stats.json, prints a structured report. Adapted from CVPR analyze.py.
# Usage: python analyze.py <draft.tex or dir>
import os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_EXTRACT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "extract.py"))
sys.path.insert(0, os.path.dirname(REPO_EXTRACT))
import extract  # noqa: E402  ponytail: one source of truth, no copy.

STATS_PATH = os.path.join(HERE, "..", "reference", "icml_stats.json")

NUMERIC_MAP = [  # (draft_path, stats_key)
    (["abstract", "sentences"],            "abstract.sentences"),
    (["abstract", "words"],                "abstract.words"),
    (["intro", "paragraphs"],               "intro.paragraphs"),
    (["related", "words"],                 "related.words"),
    (["method", "equation_count"],         "method.equation_count"),
    (["method", "figure_count"],           "method.figure_count"),
    (["experiments", "table_count"],       "experiments.table_count"),
    (["experiments", "ablation_mentions"], "experiments.ablation_mentions"),
    (["experiments", "sota_mentions"],     "experiments.sota_mentions"),
    (["claims", "body_words"],             "claims.body_words"),
    (["citations", "total"],               "citations.total"),
]
BOOL_MAP = [
    (["structure", "has_ablation_heading"], "structure.has_ablation_heading"),
    (["structure", "has_related"],          "structure.has_related"),
    (["structure", "has_conclusion"],       "structure.has_conclusion"),
    (["intro", "has_contrib_list"],          "intro.has_contrib_list"),
]

def status_for(value, q, domain_sensitive=False):
    if value is None: return "missing"
    if q is None: return "no_corpus_data"
    med, p25, p75 = q["median"], q["p25"], q["p75"]
    if value < p25 or value > p75:
        return "domain-sensitive-deviation" if domain_sensitive else "deviates"
    return "normal"

def main():
    if len(sys.argv) < 2:
        print("usage: analyze.py <draft.tex or dir>", file=sys.stderr)
        sys.exit(2)
    target = sys.argv[1]
    if os.path.isdir(target):
        paper_dir = target
        paper_id = os.path.basename(os.path.abspath(target.rstrip("/"))) or "draft"
    else:
        paper_dir = os.path.dirname(os.path.abspath(target)) or "."
        paper_id = os.path.splitext(os.path.basename(target))[0]
    feats = extract.extract_features(paper_id, paper_dir)
    if feats.get("error"):
        print(f"ERROR: {feats['error']}", file=sys.stderr)
        sys.exit(1)
    stats = json.load(open(STATS_PATH))
    print(f"# Style report: {paper_id}")
    print(f"domain (10-bucket, OpenReview-area if corpus paper else keyword): {feats.get('domain','?')}")
    print(f"domain_source: {feats.get('domain_source','?')}")
    print(f"root tex: {feats.get('root_tex','?')}\n")
    print("## Numeric fields (value | corpus median [P25-P75] | status)")
    for dpath, skey in NUMERIC_MAP:
        val = feats
        for k in dpath:
            val = val.get(k) if isinstance(val, dict) else None
        fld = stats["fields"].get(skey, {})
        q = fld.get("quantiles")
        sens = fld.get("domain_sensitive", False)
        status = status_for(val, q, sens)
        if val is None:
            line = f"- {skey:38} MISSING"
        else:
            med = q["median"] if q else "n/a"
            band = f"[{q['p25']}-{q['p75']}]" if q else "n/a"
            line = f"- {skey:38} {val:>6} | corpus median {med} {band:>12} | {status}"
        if sens:
            pd = fld.get("per_domain_median", {})
            if pd:
                line += " (domain-sensitive; closest-domain medians: " + \
                        ", ".join(f"{d}={v}" for d, v in list(pd.items())[:4]) + ")"
        print(line)
    print("\n## Boolean flags (your draft | corpus %true)")
    for dpath, skey in BOOL_MAP:
        val = feats
        for k in dpath:
            val = val.get(k) if isinstance(val, dict) else None
        fld = stats["fields"].get(skey, {})
        rate = fld.get("rate_true", "n/a")
        yn = "yes" if val else ("no" if val is False else "?")
        print(f"- {skey:40} {yn:>3} | corpus {rate}% true")
    print("\n## Citation venue share (your draft)")
    vc = feats.get("citations", {}).get("venue_counts", {})
    tot = sum(vc.values()) or 1
    for k in ("ML_conf", "CV_conf", "preprint", "journal", "other"):
        print(f"  {k}: {100*vc.get(k,0)/tot:.1f}%")
    ml_med = stats["fields"].get("citations.ML_conf_perpaper_median")
    cv_med = stats["fields"].get("citations.CV_conf_perpaper_median")
    print(f"  (corpus per-paper median: ML_conf {ml_med}%, CV_conf {cv_med}%)")
    print("\n## Section order detected")
    for s in feats["structure"]["section_order"]:
        print(f"  - {s}")

if __name__ == "__main__":
    main()