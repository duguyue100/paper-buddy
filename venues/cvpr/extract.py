#!/usr/bin/env python3
# ponytail: deterministic per-paper feature extractor for CVPR 2026 oral corpus.
# Resolves \input/\include from the root tex (the one with \documentclass),
# strips comments, runs regex extractors, emits features/<id>.json.
# Partial-safe: missing sections -> null. Counts only, never names domain tells.
# Ceiling: keyword domain tag, upgrade to embeddings if granularity matters.
import os, re, json, sys, glob

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "features")

CITATION_RE = re.compile(r"\\(?:cite|citep|citet|citeauthor|citeyear|parencite|autocite)\b")
EQ_RE = re.compile(r"\\begin\{(?:equation|align|gather|multline|eqnarray)\*?\}")
FIG_RE = re.compile(r"\\begin\{figure\*?\}")
TBL_RE = re.compile(r"\\begin\{table\*?\}")
SECTION_RE = re.compile(r"\\section\*?\s*\{")
SECTION_TITLES_RE = re.compile(r"\\section\*?\s*\{([^}]*)\}")
# ponytail: role patterns broadened from title text alone won't catch methods named after
# the contribution; method/e$$px slices are computed from the gap between known roles instead.
ROLE_INTRO_RE = re.compile(r"intro", re.I)
ROLE_RELATED_RE = re.compile(r"relat|prior\s+work", re.I)
ROLE_EXP_RE = re.compile(r"experiment|evaluat|result|comparison", re.I)
ROLE_CONCL_RE = re.compile(r"conclu|discussion", re.I)
ABLATION_RE = re.compile(r"ablation", re.I)
SUBSECTION_RE = re.compile(r"\\subsection\*?\s*\{([^}]*)\}")
ABSTRACT_RE = re.compile(r"\\begin\{abstract\}\s*(.*?)\s*\\end\{abstract\}", re.S)
ABSTRACT_STOP_RE = re.compile(r"\\(?:section|subsection|input|include|begin\{document|chapter)\b")
# ponytail: abstract appears as env, custom \abstract{...}, or manual {\centering ...\textbf{Abstract}\par} block.

def balanced_brace(text, brace_idx):
    # ponytail: returns content inside {...} starting at text[brace_idx]=='{', handles nesting.
    if brace_idx < 0 or text[brace_idx] != "{":
        return None
    depth = 0
    for i in range(brace_idx, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[brace_idx + 1:i]
    return None  # unbalanced

def extract_abstract(full_text):
    # ponytail: abstract may live in body env, as preamble macro \abstract{...},
    # or a standalone file not input from root. Search full_text then fall back to dir scan.
    m = ABSTRACT_RE.search(full_text)
    if m:
        return m.group(1)
    # \abstract{ ... } custom macro (often precedes \begin{document})
    for key in (r"\abstract", r"\abs"):
        i = full_text.find(key + "{")
        if i >= 0:
            bj = full_text.find("{", i + len(key))
            if bj >= 0:
                c = balanced_brace(full_text, bj)
                if c and len(c) > 20:
                    return c
    # manual block: marked with \textbf{Abstract}\par}{ then prose until next section/input
    m = re.search(r"\\textbf\{(Abstract|ABSTRACT)\}\\?par?\}", full_text)
    if m:
        rest = full_text[m.end():]
        stop = ABSTRACT_STOP_RE.search(rest)
        return rest[:stop.start()] if stop else rest
    return None

def extract_abstract_with_fallback(full_text, paper_dir):
    abs_text = extract_abstract(full_text)
    if abs_text:
        return abs_text
    # ponytail: standalone abstract file not input from root (rare). Scan dir .tex files.
    for root, _, files in os.walk(paper_dir):
        for f in files:
            if not f.endswith(".tex") or "abstract" not in f.lower():
                continue
            p = os.path.join(root, f)
            try:
                with open(p, encoding="utf-8", errors="ignore") as fh:
                    txt = fh.read()
            except OSError:
                continue
            cand = extract_abstract(txt)
            if cand:
                return cand
    return None
TITLE_RE = re.compile(r"\\title\*?\s*\{([^}]*?)\}", re.S)
INPUT_RE = re.compile(r"\\(?:input|include)\s*\{([^}]*)\}")
# ponytail: regex bibtex scanner. Robust enough for citation venue breakdown; no bibtexparser dep.
BIB_ENTRY_RE = re.compile(r"@\w+\s*\{([^,]+),\s*(.*?)\n\}", re.S)
BIB_FIELD_RE = re.compile(r"(author|title|journal|booktitle|bookTitle|publisher)\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", re.S)
VENUE_PATTERNS = [
    # CV_conf: CV-family (acronyms + spelled-out forms used by @String macros)
    ("CV_conf", re.compile(
        r"\b(CVPR|ICCV|ECCV|ACCV|CVPRW|WACV)\b"
        r"|Comput\.\s*Vis\.\s*Pattern\s*Recog"
        r"|Conf\.\s*Comput\.\s*Vis"
        r"|Int\.\s*Conf\.\s*on\s*Comput\.\s*Vis"
        r"|European\s*Conf\.\s*Comput\.\s*Vis"
        r"|Computer\s*Vision\s*and\s*Pattern\s*Recogn", re.I)),
    # ML_conf: ML-family
    ("ML_conf", re.compile(
        r"\b(ICML|ICLR|NeurIPS|NIPS|COLM)\b"
        r"|Int\.\s*Conf\.\s*Mach\.\s*Learn"
        r"|Int\.\s*Conf\.\s*Learn\.\s*Represent"
        r"|Conf\.\s*on\s*Neural\s*Inform"
        r"|Adv\.\s*Neural\s*Inform", re.I)),
    # Preprint: arxiv
    ("preprint", re.compile(r"\barxiv\b", re.I)),
    # Journal
    ("journal", re.compile(
        r"\b(IEEE|ACM)\b|TPAMI|IJCV|CVGIP|Nature|Science|JMLR|TIM|TIP"
        r"|Trans\.\s*Pattern\s*Anal"
        r"|Trans\.\s*Image\s*Process"
        r"|Pattern\s*Anal\.\s*Mach\.\s*Intell"
        r"|Trans\.\s*Vis\.\s*Comput\.\s*Graph"
        r"|Int\.\s*J\.\s*Comput\.\s*Vis"
        r"|Pattern\s*Recogn", re.I)),
]
HEDGE = re.compile(r"\b(can|may|might|could|typically|usually|often|in general|tends to|may not|might not|often do not)\b", re.I)
SUPERL = re.compile(r"\b(state-of-the-art|SOTA|outperform|novel|first to|best|superior|surpass)\b", re.I)
CONTRIB_RE = re.compile(r"(our|the)\s+(key\s+|main\s+)?contributions?\s+(are|is|include|summariz)", re.I)
CONTRIB_ITEM_RE = re.compile(r"\\(?:item|textbf)\b")
OPENING_VERB_RE = re.compile(r"\bwe\s+(propose|present|introduce|describe|build|design|develop|investigate|explore|study|address|tackle|leverag\w+|formulat\w+|aim|show|demonstrate)\b", re.I)

DOMAIN_KW = [
    ("3D", r"\b(3-?D|Gaussian\s+splat|splatting|NeRF|radiance|mesh|6-?DOF|SLAM|point\s+cloud|voxel|novel\s+view)\b"),
    ("video", r"\b(video|temporal|frame\b|action\s+recognition|optical\s+flow)\b"),
    ("medical", r"\b(medical|clinical|histopath|WSI|slide|CT\b|M(?!LLM)RI\b|lesion|tumor|cancer)\b"),
    ("generation", r"\b(diffusion|generative|synthesi\w+|text-to-|image\s+generation)\b"),
    ("VL", r"\b(vision-language|vision\s+language|VLM|MLLM|multimodal|CLIP|LLM|large\s+language)\b"),
    ("segdet", r"\b(segmentation|detection|instance)\b"),
    ("SSL", r"\b(self-supervised|contrastive|representation\s+learning|pretrain)\b"),
    ("security", r"\b(adversarial|robust\w*\s+attack|privacy|attack\b|defense)\b"),
    ("efficiency", r"\b(efficient|accelerat|pruning|quantiz|distill|lightweight)\b"),
]

def strip_comments(text):
    # ponytail: LaTeX comments run to EOL; \% is literal.
    return "\n".join(re.sub(r"(?<!\\)%.*", "", ln) for ln in text.splitlines())

def find_root_tex(paper_dir):
    # root = the .tex (recursively, depth<=3) containing \documentclass.
    cands = []
    for root, _, files in os.walk(paper_dir):
        depth = root[len(paper_dir):].count(os.sep)
        if depth > 3:
            continue
        for f in files:
            if f.endswith(".tex"):
                cands.append(os.path.join(root, f))
    # ponytail: prefer conventional main/arxiv/paper names over supplementary/rebuttal.
    def root_score(p):
        nm = os.path.basename(p).lower()
        pref = 0
        for k, w in [("main.tex", -3), ("arxiv.tex", -3), ("paper.tex", -3), ("main", -2)]:
            if k in nm:
                pref = w
                break
        # avoid supplementary/rebuttal/appendix when alternatives exist
        for bad in ("supp", "rebuttal", "appendix", "supplementary"):
            if bad in nm:
                pref = max(pref, 1)
        return (os.path.relpath(p, paper_dir).count(os.sep), pref, len(p))
    for c in sorted(cands, key=root_score):
        try:
            with open(c, encoding="utf-8", errors="ignore") as fh:
                if re.search(r"\\documentclass", fh.read()):
                    return c
        except OSError:
            pass
    # fall back: shallowest .tex with \begin{document}
    for c in sorted(cands, key=lambda p: (p.count(os.sep), len(p))):
        try:
            with open(c, encoding="utf-8", errors="ignore") as fh:
                if re.search(r"\\begin\{document\}", fh.read()):
                    return c
        except OSError:
            pass
    return cands[0] if cands else None

def resolve_inputs(path, base_dir, seen=None):
    # ponytail: recursively inline \input/\include; cycle guard.
    if seen is None:
        seen = set()
    rp = os.path.realpath(path)
    if rp in seen:
        return ""
    seen.add(rp)
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            raw = fh.read()
    except OSError:
        return ""
    out = []
    for ln in raw.splitlines():
        m = INPUT_RE.search(ln)
        if m:
            inc = m.group(1).strip()
            # try several resolutions
            for cand in (inc, inc + ".tex",
                         os.path.join(base_dir, inc),
                         os.path.join(base_dir, inc + ".tex")):
                if os.path.isfile(cand):
                    out.append(resolve_inputs(cand, os.path.dirname(cand) or base_dir, seen))
                    break
            # unresolved input: skip silently (partial-safe)
        else:
            out.append(ln)
    return "\n".join(out)

def get_body(text):
    m = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", text, re.S)
    return m.group(1) if m else text

def count_sentences(text):
    clean = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})*", " ", text)
    clean = re.sub(r"[{}\\]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return 0
    return len(re.findall(r"[.!?]\s", clean + " "))

def count_words(text):
    clean = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})*", " ", text)
    clean = re.sub(r"[{}\\]", " ", clean)
    return len(re.findall(r"[A-Za-z][A-Za-z\-']*", clean))

def first_sentence(text):
    clean = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})*", " ", text)
    clean = re.sub(r"[{}\\]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    m = re.match(r"(.*?[.!?])\s", clean)
    return m.group(1) if m else clean[:200]

def detect_domain(title, abstract):
    blob = (title or "") + " " + (abstract or "")
    for label, pat in DOMAIN_KW:
        if re.search(pat, blob, re.I):
            return label
    return "other"

def find_role_idx(sections, pattern):
    for i, s in enumerate(sections):
        if pattern.search(s):
            return i
    return None

def section_spans(body, sections):
    # ponytail: anchor on the \section command position, not body.find(title) which
    # would match the same title mentioned in another section's prose (false start).
    matches = list(SECTION_TITLES_RE.finditer(body))
    spans = []
    for i, _ in enumerate(sections):
        if i < len(matches):
            start = matches[i].start()
        elif spans:
            start = spans[-1][1]
        else:
            start = 0
        end = matches[i + 1].start() if (i + 1) < len(matches) else len(body)
        if start < 0:
            start = (spans[-1][1] if spans else 0)
        spans.append((start, end))
    return spans

def classify_bib_venue(field_blob):
    # ponytail: scan journal/booktitle field text; first matching venue family wins.
    for venue, pat in VENUE_PATTERNS:
        if pat.search(field_blob):
            return venue
    return "other"

def scan_bib_venues(paper_dir):
    # ponytail: find .bib files, resolve @String macros, scan entries, count venue families.
    counts = {"CV_conf": 0, "ML_conf": 0, "preprint": 0, "journal": 0, "other": 0}
    found_any = False
    macro_re = re.compile(r"@String\s*\{\s*(\w+)\s*=\s*\{([^}]*)\}\s*\}", re.I)
    # field value: either {...} or a bare token (resolved via macro)
    field_re = re.compile(r"(?:journal|booktitle|bookTitle)\s*=\s*(?:\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}|([A-Za-z][\w\-]*))", re.S)
    for root, _, files in os.walk(paper_dir):
        for f in files:
            if not f.endswith(".bib"):
                continue
            try:
                with open(os.path.join(root, f), encoding="utf-8", errors="ignore") as fh:
                    txt = fh.read()
            except OSError:
                continue
            found_any = True
            macros = {k: v for k, v in macro_re.findall(txt)}
            for m in BIB_ENTRY_RE.finditer(txt):
                blob = m.group(2)
                fm = field_re.search(blob)
                if fm:
                    v_in = fm.group(1)
                    v_tok = fm.group(2)
                    if v_in is not None:
                        val = v_in + " " + v_tok if v_tok else v_in
                    elif v_tok:
                        val = macros.get(v_tok, "") + " " + v_tok
                    else:
                        val = ""
                else:
                    val = blob[:60]
                counts[classify_bib_venue(val if val else blob[:60])] += 1
    return counts, found_any

def extract_method_name(title, body):
    # ponytail: heuristic - a capitalized/acronym token near "we (propose|present|call)"
    m = re.search(r"we\s+(?:propose|present|introduce|call)\s+(?:it\s+)?\\?(?:textbf|emph)?\s*\{?\s*([A-Z][A-Za-z0-9\-]{2,})", body)
    if m:
        return m.group(1)
    m = re.search(r",\s+(?:named|called)\s+([A-Z][A-Za-z0-9\-]{2,})", body)
    return m.group(1) if m else None

def extract_features(paper_id, paper_dir):
    root = find_root_tex(paper_dir)
    if not root:
        return {"id": paper_id, "error": "no_tex", "root_tex": None}
    full = resolve_inputs(root, paper_dir)
    full_nc = strip_comments(full)
    body = get_body(full_nc)

    abs_m = extract_abstract_with_fallback(full_nc, paper_dir)
    abstract = abs_m if abs_m else None
    title_m = TITLE_RE.search(full_nc)
    title = title_m.group(1).strip() if title_m else None
    # title may use \input; if short/empty, fall back to first \section before abstract
    if not title:
        title = ""

    sections = SECTION_TITLES_RE.findall(body)
    subsections = SUBSECTION_RE.findall(body)
    has_abl = any(ABLATION_RE.search(s) for s in sections + subsections)
    abl_table_count = len(ABLATION_RE.findall(body))

    spans = section_spans(body, sections)
    intro_idx = find_role_idx(sections, ROLE_INTRO_RE)
    related_idx = find_role_idx(sections, ROLE_RELATED_RE)
    exp_idx = find_role_idx(sections, ROLE_EXP_RE)
    concl_idx = find_role_idx(sections, ROLE_CONCL_RE)

    def slice_idx(i):
        if i is None or i >= len(spans):
            return ""
        return body[spans[i][0]:spans[i][1]] if spans[i][0] >= 0 else ""

    intro_text = slice_idx(intro_idx)
    related_words = count_words(slice_idx(related_idx)) if related_idx is not None else 0

    # ponytail: method block = sections between intro/related and experiments/conclusion,
    # name-agnostic so methods titled after the contribution are caught.
    anchor_end = (related_idx if related_idx is not None else intro_idx)
    block_end = exp_idx if exp_idx is not None else concl_idx
    has_method_block = anchor_end is not None and \
        ((block_end is not None and block_end > anchor_end + 1) or
         (block_end is None and len(sections) > (anchor_end or 0) + 1))
    method_text = ""
    if has_method_block and anchor_end is not None:
        m_start = spans[anchor_end + 1][0]
        m_end = spans[block_end][0] if block_end is not None else len(body)
        method_text = body[m_start:m_end] if m_start >= 0 else ""

    # intro paragraph count (blank-line separated)
    intro_paras = len([p for p in re.split(r"\n\s*\n", intro_text) if p.strip()]) if intro_text else 0
    has_contrib = bool(CONTRIB_RE.search(intro_text)) if intro_text else False
    contrib_items = len(CONTRIB_ITEM_RE.findall(intro_text)) if intro_text else 0

    hook = None
    if intro_text:
        fs = first_sentence(intro_text)
        if fs.endswith("?"):
            hook = "question"
        elif re.search(r"\d+\s*%|\d+\s*(million|billion|thousand)|\b\d{4}\b", fs):
            hook = "statistic"
        elif fs.startswith('"') or fs.startswith("'"):
            hook = "quote"
        else:
            hook = "claim"

    opening_verb = None
    if abstract:
        m = OPENING_VERB_RE.search(abstract)
        if m:
            opening_verb = m.group(1).lower()

    abs_sentences = count_sentences(abstract) if abstract else None
    abs_words = count_words(abstract) if abstract else None

    total_citations = len(CITATION_RE.findall(body))
    eq_count = len(EQ_RE.findall(body))
    fig_count = len(FIG_RE.findall(body))
    tbl_count = len(TBL_RE.findall(body))
    sota_mentions = len(SUPERL.findall(body))
    hedge_count = len(HEDGE.findall(body))

    method_name = extract_method_name(title, intro_text or body)
    venue_counts, bib_found = scan_bib_venues(paper_dir)

    body_words = count_words(body)
    features = {
        "id": paper_id,
        "domain": detect_domain(title, abstract or ""),
        "root_tex": os.path.relpath(root, paper_dir),
        "structure": {
            "section_order": sections,
            "section_count": len(sections),
            "has_abstract": abstract is not None,
            "has_intro": intro_idx is not None,
            "has_related": related_idx is not None,
            "has_method": has_method_block,
            "has_experiments": any(re.search(r"experiment|evaluat|result", s.lower()) for s in sections),
            "has_conclusion": any(re.search(r"conclu", s.lower()) for s in sections),
            "has_ablation_heading": has_abl,
        },
        "abstract": {
            "sentences": abs_sentences,
            "words": abs_words,
            "opening_verb": opening_verb,
            "has_contrib_list": bool(CONTRIB_RE.search(abstract)) if abstract else False,
        },
        "intro": {
            "paragraphs": intro_paras or None,
            "has_contrib_list": has_contrib,
            "contrib_item_count": contrib_items if has_contrib else 0,
            "hook_type": hook,
        },
        "related": {"words": related_words or None},
        "method": {
            "name": method_name,
            "equation_count": eq_count if method_text else None,
            "figure_count": len(FIG_RE.findall(method_text)) if method_text else None,
        },
        "experiments": {
            "table_count": tbl_count,
            "has_ablation": has_abl,
            "ablation_mentions": abl_table_count,
            "sota_mentions": sota_mentions,
        },
        "claims": {
            "body_words": body_words,
            "hedging_count": hedge_count,
            "superlative_count": sota_mentions,
        },
        "citations": {
            "total": total_citations,
            "bib_found": bib_found,
            "venue_counts": venue_counts,
        },
    }
    return features

def main():
    os.makedirs(OUT, exist_ok=True)
    dirs = sorted(d for d in os.listdir(DATA)
                  if os.path.isdir(os.path.join(DATA, d)))
    n_ok = n_err = 0
    for d in dirs:
        out_path = os.path.join(OUT, d + ".json")
        if os.path.exists(out_path):  # ponytail: idempotent re-runs
            n_ok += 1
            continue
        try:
            feats = extract_features(d, os.path.join(DATA, d))
            with open(out_path, "w") as fh:
                json.dump(feats, fh, indent=2)
            if feats.get("error"):
                n_err += 1
                print(f"[err] {d}: {feats['error']}", file=sys.stderr)
            else:
                n_ok += 1
                print(f"[ok] {d}: domain={feats['domain']} secs={feats['structure']['section_count']} "
                      f"abs_s={feats['abstract']['sentences']}", file=sys.stderr)
        except Exception as e:
            n_err += 1
            print(f"[exc] {d}: {e}", file=sys.stderr)
    print(f"[done] ok={n_ok} err={n_err} out={OUT}", file=sys.stderr)

if __name__ == "__main__":
    main()
