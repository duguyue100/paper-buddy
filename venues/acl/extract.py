#!/usr/bin/env python3
# ponytail: deterministic per-paper feature extractor for ACL 2026 oral corpus.
# Adapted from ICML extract.py (same LaTeX extractors, same partial-safe design,
# same method-block anchoring at intro_idx+1 ending at earliest-of-experiments/conclusion).
# Three deltas vs ICML:
#   1. No OpenReview primary_area path (ACL has no OpenReview). Domain tag uses a single
#      keyword classifier over title+abstract with a 10-bucket NLP vocabulary inspired by
#      ACL's official submission tracks. Same keyword path is used for drafts, so corpus
#      and draft are tagged through one consistent code path.
#   2. Citation venue patterns rewired: NLP_conf is the primary venue family
#      (ACL/EMNLP/NAACL/COLING/TACL/Findings/Human Language Technologies/FSMNLP),
#      ML_conf is the academic ML family (ICML/ICLR/NeurIPS/COLT/AISTATS/UAI/IJCAI/AAAI/
#      KDD/SIGIR/WWW/WSDM), CV_conf is secondary. Includes spelled-out long forms common
#      in NLP bibs ("Twelfth Learning Representations" for ICLR, "Computing Research
#      Repository" for arXiv/CoRR, "Transactions of the Association for Computational
#      Linguistics" for TACL).
#   3. Domain buckets: 10 NLP-appropriate labels with keyword patterns chosen to overlap
#      ACL tracks where useful (Language Modeling -> llm_reasoning; Generation +
#      Summarization + Machine Translation -> generation; Information Retrieval and Text
#      Mining -> retrieval_rag; Information Extraction + Sentiment Analysis/Argument Mining
#      -> ie_classification; Question Answering -> qa; Multimodality -> multimodal;
#      Syntax/Semantics/Phonology/Morphology/Discourse -> parsing_linguistic;
#      Interpretability + Ethics/Bias/Fairness -> interpretability; Efficient Methods for
#      NLP -> efficiency; everything else falls to "other").
import os, re, json, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "features")

CITATION_RE = re.compile(r"\\(?:cite|citep|citet|citeauthor|citeyear|parencite|autocite)\b")
EQ_RE = re.compile(r"\\begin\{(?:equation|align|gather|multline|eqnarray)\*?\}")
FIG_RE = re.compile(r"\\begin\{figure\*?\}")
TBL_RE = re.compile(r"\\begin\{table\*?\}")
SECTION_RE = re.compile(r"\\section\*?\s*\{")
SECTION_TITLES_RE = re.compile(r"\\section\*?\s*\{([^}]*)\}")
ROLE_INTRO_RE = re.compile(r"intro", re.I)
# ponytail: tightened per ICML learnings — "related (work|research|literature|studies)"
# or "prior/previous work"; "background and related" stays. Bare "Background" left out
# because NLP method sections often have a "Background" subsection that is NOT the same
# role as Related Work, and matching it would inflate the related-word metric.
ROLE_RELATED_RE = re.compile(r"\brelated\s+(?:works?|research|literature|studies)|prior\s+works?|previous\s+works?|background\s+and\s+related", re.I)
ROLE_EXP_RE = re.compile(r"experiment|evaluat|result|comparison", re.I)
ROLE_CONCL_RE = re.compile(r"conclu|discussion", re.I)
ABLATION_RE = re.compile(r"ablation", re.I)
SUBSECTION_RE = re.compile(r"\\subsection\*?\s*\{([^}]*)\}")
ABSTRACT_RE = re.compile(r"\\begin\{abstract\}\s*(.*?)\s*\\end\{abstract\}", re.S)
ABSTRACT_STOP_RE = re.compile(r"\\(?:section|subsection|input|include|begin\{document|chapter)\b")

# ponytail: 10 NLP-appropriate domain buckets. Aligned to ACL's official submission tracks
# where possible; keyword patterns discriminate by NLP task/structure. Title+abstract are
# usually enough signal — keep patterns target to the title/abstract blob.
DOMAIN_KW = [
    ("llm_reasoning", r"\b(large\s+language|LLM\b|GPT\b|instruction[-\s]?tun|in-?context\s+learn|chain[-\s]?of[-\s]?thought|\bagent|RLHF|assistant\b|code\s+model|code\s+generation|symbolic\s+reason|language\s+modell?|pretrain(?:ed)?\s+language)\b"),
    ("generation", r"\b(generation|generat\w*|summariz|machine\s+translat|\bMT\b|dialogue|dialog\s+system|response\s+gen|natural\s+language\s+gen|\bNLG\b|long-?form)\b"),
    ("retrieval_rag", r"\b(retriev|RAG\b|dense\s+retriev|passage\s+retriev|knowledge[-\s]ground|text\s+min|\bIR\s+system)\b"),
    ("ie_classification", r"\b(named\s+entity|\bNER\b|relation\s+extract|information\s+extract|sentiment|stance\s+detect|emotion\s+class|argument\s+min|stylist|aspect[-\s]based)\b"),
    ("qa", r"\b(question\s+answer|reading\s+compreh|\bQA\b|\bQ&A\b|open[-\s]?book)\b"),
    ("multimodal", r"\b(vision[-\s]?language|vision\s+language|\bVLM\b|visual\s+question|video[-\s]?\w*\s*language|image[-\s]?text|multimodal|grounded|clip\s+model|embodi\w*)\b"),
    ("parsing_linguistic", r"\b(syntax|\bpars(?:e|ing)\b|TAGging|chunk|dependency|semantic\s+pars|phonolog|morpholog|word\s+seg|discourse|pragmatic|constituen|lexical\s+semantics)\b"),
    ("interpretability", r"\b(interpretab|explainab|probing|probe\s+study|bias\s+(?:detect|analys)|fairness|ethical|toxic\w*|stereo\w*|red[-\s]?team)\b"),
    ("efficiency", r"\b(efficient|distill|pruning|quantiz|compress\w*|lightweight|low-?resource\s+infer|on-?device)\b"),
]

def balanced_brace(text, brace_idx):
    if brace_idx < 0 or text[brace_idx] != "{":
        return None
    depth = 0
    for i in range(brace_idx, len(text)):
        c = text[i]
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: return text[brace_idx + 1:i]
    return None

def extract_abstract(full_text):
    m = ABSTRACT_RE.search(full_text)
    if m: return m.group(1)
    for key in (r"\abstract", r"\abs"):
        i = full_text.find(key + "{")
        if i >= 0:
            bj = full_text.find("{", i + len(key))
            if bj >= 0:
                c = balanced_brace(full_text, bj)
                if c and len(c) > 20: return c
    m = re.search(r"\\textbf\{(Abstract|ABSTRACT)\}\\?par?\}", full_text)
    if m:
        rest = full_text[m.end():]
        stop = ABSTRACT_STOP_RE.search(rest)
        return rest[:stop.start()] if stop else rest
    return None

def extract_abstract_with_fallback(full_text, paper_dir):
    abs_text = extract_abstract(full_text)
    if abs_text: return abs_text
    for root, _, files in os.walk(paper_dir):
        for f in files:
            if not f.endswith(".tex") or "abstract" not in f.lower(): continue
            p = os.path.join(root, f)
            try:
                with open(p, encoding="utf-8", errors="ignore") as fh: txt = fh.read()
            except OSError: continue
            cand = extract_abstract(txt)
            if cand: return cand
    return None

TITLE_RE = re.compile(r"\\title\*?\s*\{([^}]*?)\}", re.S)
INPUT_RE = re.compile(r"\\(?:input|include)\s*\{([^}]*)\}")
# ponytail: bibtex scanner. The lazy-`.*?\n}` regex used by the CVPR/ICML extractors
# catastrophically backtracks on the 30–46 MB "anthology.bib" some ACL papers bundle
# (the full ACL Anthology references file). Replaced by a char-walking balanced-brace
# scanner (O(n), no backtracking) keyed on `@\w+{key,` markers.
BIB_ENTRY_START_RE = re.compile(r"@\w+\s*\{([^,]+),")
BIB_FIELD_RE = re.compile(r"(author|title|journal|booktitle|bookTitle|publisher)\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", re.S)

def iter_bib_entries(txt):
    # Yields (key, body) for each @entry{key, ...}. Brace-walks to skip nested braces.
    n = len(txt); pos = 0
    for m in BIB_ENTRY_START_RE.finditer(txt):
        # Skip entries nested inside another @comment{...} or similar — start exactly at `@`.
        if m.start() < pos:
            continue
        depth = 1; i = m.end()
        while i < n and depth > 0:
            c = txt[i]
            if c == '{': depth += 1
            elif c == '}': depth -= 1
            i += 1
        if depth == 0:
            yield m.group(1), txt[m.end():i - 1]
            pos = i

# ponytail: ACL papers cite NLP venues heavily. NLP_conf is the dominant family for ACL
# papers; ML_conf is the academic ML family (ICML/ICLR/NeurIPS/...); CV_conf secondary
# (only multimodal NLP papers cite much computer vision). Patterns include the spelled-out
# long forms that NLP bibs actually use ("Twelfth Learning Representations" for ICLR,
# "Human Language Technologies" for NAACL-HLT, "Transactions of the Association for
# Computational Linguistics" for TACL, "Computing Research Repository" for CoRR/arXiv,
# "Findings of the Association for Computational Linguistics: EMNLP").
VENUE_PATTERNS = [
    # NLP_conf: the *ACL family + sibling NLP venues + the ACL flagship journal.
    ("NLP_conf", re.compile(
        r"\b(ACL|EMNLP|NAACL|COLING|TACL|EACL|AACL|CONLL|LREC|FSMNLP|BEA)\b"
        r"|Annual\s+(?:Meeting\s+of\s+(?:the\s+)?Association\s+for\s+)?Computational\s+Linguist"
        r"|\bComputational\s+Linguistics\b"
        r"|Empirical\s+Methods\s+in\s+Natural\s+Language\s+Process"
        r"|Conf\w*\s+on\s+Empirical\s+Methods\s+in\s+Natural\s+Language"
        r"|North\s+American\s+(?:Chapter\s+of\s+the\s+Association\s+for\s+)?Computational\s+Linguist"
        r"|Human\s+Language\s+Technologies"
        r"|NAACL-?HLT"
        r"|International\s+Conf\w*\s+on\s+Computational\s+Linguist"
        r"|Transactions\s+of\s+(?:the\s+)?Association\s+for\s+Computational\s+Linguist"
        r"|Trans(?:actions?|\.)?\s+(?:of\s+)?(?:the\s+)?Assoc(?:iation|\.)?\s+(?:for\s+)?Comput\w*\.?\s*Linguist"
        r"|Findings\s+of\s+(?:the\s+)?Association\s+for\s+Computational\s+Linguist"
        r"|European\s+Chapter\s+of\s+(?:the\s+)?ACL"
        r"|Asia-?Pacific\s+Chapter\s+of\s+(?:the\s+)?ACL"
        r"|Int\.\s+Conf\.\s+on\s+(?:Computational\s+Linguist|Finite[-\s]State\s+Methods\s+and\s+NLP)"
        r"|(?:Innovative\s+Use\s+of\s+NLP|Building\s+Educational\s+Applications)"
        r"|Language\s+Resources\s+and\s+Evaluation\b",
        re.I)),
    # ML_conf: academic ML family (often the second-most for ACL papers).
    ("ML_conf", re.compile(
        r"\b(ICML|ICLR|NeurIPS|NIPS|COLM|COLT|AISTATS|UAI|IJCAI|AAAI|KDD|SIGIR|WWW|WSDM|SODA|STOC|FOCS)\b"
        r"|Int\w*\s+Conf\w*\s+(?:on\s+)?Machine\s+Learn"
        r"|Int\.\s+Conf\.\s+on\s+Mach\.\s*Learn"
        r"|Int\w*\s+Conf\w*\s+(?:on\s+)?Learning\s+Representations?"
        r"|\w*\s*Learning\s+Representations"            # "Twelfth Learning Representations", "Learning Representations"
        r"|Int\.\s+Conf\.\s+Learn\.\s*Represent"
        r"|Conf\w*\s+on\s+(?:Neural\s+Information|Learning\s+Theory|Uncertainty\s+(?:in\s+)?Artificial\s+Intelligence)"
        r"|Adv\w*\s+in\s+Neural\s+Information\s+Process\w*\s+Systems"
        r"|AAAI\s+Conf"
        r"|Int\.\s+Joint\s+Conf\.\s+AI"
        r"|Conference\s+on\s+Language\s+Modeling"
        r"|ACM\s+SIGKDD"
        r"|ACM\s+Web\s+Search\s+Data\s+Min"
        r"|ACM\s+SIGIR\s+Conf",
        re.I)),
    # CV_conf: computer vision family (mostly cited by multimodal NLP papers).
    ("CV_conf", re.compile(
        r"\b(CVPR|ICCV|ECCV|ACCV|CVPRW|WACV|BMVC)\b"
        r"|Comput\.\s*Vis\.\s*Pattern\s*Recog"
        r"|Conf\.\s+Comput\.\s*Vis"
        r"|Int\.\s+Conf\.\s+on\s+Comput\.\s*Vis"
        r"|European\s+(?:Conf(?:erence)?\.?\s+)?Comput\w*\.\s*Vis"
        r"|European\s+Conf\w*\s+on\s+Comput\w*\s+Vis"
        r"|Computer\s*Vision\s+and\s+Pattern\s*Recogn", re.I)),
    # preprint: arxiv/CoRR. ACL bibs heavily use "Computing Research Repository" form.
    ("preprint", re.compile(
        r"\b(arXiv|CoRR|OpenReview)\b"
        r"|Computing\s+Research\s+Repository",
        re.I)),
    # journal: IEEE/ACM family + ML/AI/statistics/psych/transportation journals ACL cites.
    # Spelled-out long forms included ("Journal of Machine Learning Research" for JMLR,
    # "National Academy of Sciences" for PNAS, "Journal of the ACM" for JACM) — these appear
    # often because @string macros are sometimes inlined by authors.
    ("journal", re.compile(
        r"\b(IEEE|ACM|TPAMI|IJCV|JMLR|TMLR|TACL|TIT\b|TIM\b|TIP\b|TAFFC\b|JACM\b)\b"
        r"|Trans\w*\s+Pattern\s+Anal"
        r"|J\.\s*Mach\.\s+Learn\.\s*Res"
        r"|Journal\s+of\s+Machine\s+Learning\s+Research"
        r"|Transactions\s+(?:of|on)\s+Machine\s+Learning\s+Research"
        r"|Journal\s+of\s+(?:the\s+)?ACM"
        r"|Journal\s+of\s+(?:the\s+)?Association\s+for\s+Computing\s+Machinery"
        r"|Journal\s+of\s+Computing\s+and\s+Machinery"
        r"|Trans\w*\s+Image\s+Process"
        r"|Trans\w*\s+(?:of|on)\s+(?:the\s+)?Association\s+for\s+Comput"
        r"|Trans\w*\s+Information\s+Theory"
        r"|Trans\.\s*Mach\.\s*Learn\.\s*Res\."
        r"|Int\.\s+J\.\s+Comput\.\s*Vis"
        r"|Nat(?:ure)?\b|Science\b|PNAS\b|National\s+Academy\s+of\s+Sciences"
        r"|Artificial\s+Intelligence\b"
        r"|Bernoulli\b|Biometrika\b|Bayesian\s+Analysis"
        r"|J\.\s+Roy\.\s*Statist\.\s*Soc|J\.\s+Am\.\s+Stat(?:ist)?\.\s+Assoc\b"
        r"|Journal\s+of\s+the\s+(?:American\s+Statistical\s+Assoc|Royal\s+Statistical\s+Soc)"
        r"|Ann\.\s+Appl\.\s+Probab|Annals\s+of\s+Applied\s+Probability"
        r"|Statistics\s+and\s+Computing"
        r"|Pattern\s+Anal\.\s*Mach\.\s*Intell"
        r"|Operations\s+Research\b"
        r"|(?:Neural|Information)\s+Computation\b|Neural\s+Networks\b|Information\s+Sciences\b"
        r"|Neurocomputing\b|Neural\s+Computing\s+and\s+Applications"
        r"|Scientific\s+Reports\b"
        r"|Knowledge[-\s]Based\s+Systems"
        # psychology / education / social science journals (psychometric NLP papers cite):
        r"|Psychometrika|Psychological\s+(?:Review|Bulletin)|Multivariate\s+Behavioral\s+Research"
        r"|Educational\s+and\s+Psychological\s+Measurement|Applied\s+Psychological\s+Measurement"
        r"|Educational\s+Researcher|Psychological\s+Methods|Behavior\s+Research\s+Methods"
        r"|British\s+Journal\s+of\s+Mathematical\s+and\s+Statistical\s+Psychology"
        r"|Journal\s+of\s+(?:Educational\s+(?:and\s+Behavioral\s+)?Statistics|Educational\s+Measurement|Statistical\s+Software)"
        r"|Cognition\b|Journal\s+of\s+Memory\s+and\s+Language"
        # transportation journals cited by NLP-for-transportation papers:
        r"|Transportation\s+Research\s+(?:Part\s+[A-Z]|Record|Procedia)",
        re.I)),
]
HEDGE = re.compile(r"\b(can|may|might|could|typically|usually|often|in general|tends to|may not|might not|often do not)\b", re.I)
SUPERL = re.compile(r"\b(state-of-the-art|SOTA|outperform|novel|first to|best|superior|surpass)\b", re.I)
CONTRIB_RE = re.compile(r"(our|the)\s+(key\s+|main\s+)?contributions?\s+(are|is|include|summariz)", re.I)
CONTRIB_ITEM_RE = re.compile(r"\\(?:item|textbf)\b")
OPENING_VERB_RE = re.compile(r"\bwe\s+(propose|present|introduce|describe|build|design|develop|investigate|explore|study|address|tackle|leverag\w+|formulat\w+|aim|show|demonstrate)\b", re.I)

def strip_comments(text):
    return "\n".join(re.sub(r"(?<!\\)%.*", "", ln) for ln in text.splitlines())

def find_root_tex(paper_dir):
    # root = the .tex (recursively, depth<=3) containing \documentclass.
    cands = []
    for root, _, files in os.walk(paper_dir):
        depth = root[len(paper_dir):].count(os.sep)
        if depth > 3: continue
        for f in files:
            if f.endswith(".tex"): cands.append(os.path.join(root, f))
    # ponytail: prefer conventional ACL/main/arxiv names over supplementary/rebuttal.
    def root_score(p):
        nm = os.path.basename(p).lower()
        pref = 0
        for k, w in [("main.tex", -3), ("arxiv.tex", -3), ("paper.tex", -3),
                     ("acl_latex.tex", -3), ("acl.tex", -3),
                     ("emnlp2023.tex", -3), ("emnlp2024.tex", -3),
                     ("naacl.tex", -3),
                     ("main", -2), ("acl", -2)]:
            if k in nm: pref = w; break
        for bad in ("supp", "rebuttal", "appendix", "supplementary"):
            if bad in nm: pref = max(pref, 1)
        return (os.path.relpath(p, paper_dir).count(os.sep), pref, len(p))
    for c in sorted(cands, key=root_score):
        try:
            with open(c, encoding="utf-8", errors="ignore") as fh:
                if re.search(r"\\documentclass", fh.read()): return c
        except OSError: pass
    for c in sorted(cands, key=lambda p: (p.count(os.sep), len(p))):
        try:
            with open(c, encoding="utf-8", errors="ignore") as fh:
                if re.search(r"\\begin\{document\}", fh.read()): return c
        except OSError: pass
    return cands[0] if cands else None

def resolve_inputs(path, base_dir, seen=None):
    if seen is None: seen = set()
    rp = os.path.realpath(path)
    if rp in seen: return ""
    seen.add(rp)
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh: raw = fh.read()
    except OSError: return ""
    out = []
    for ln in raw.splitlines():
        m = INPUT_RE.search(ln)
        if m:
            inc = m.group(1).strip()
            for cand in (inc, inc + ".tex", os.path.join(base_dir, inc),
                         os.path.join(base_dir, inc + ".tex")):
                if os.path.isfile(cand):
                    out.append(resolve_inputs(cand, os.path.dirname(cand) or base_dir, seen))
                    break
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
    if not clean: return 0
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
    # ponytail: single code path for corpus papers AND drafts. Try title+abstract;
    # first matching bucket wins (DOMAIN_KW order places more specific buckets first).
    blob = (title or "") + "\n" + (abstract or "")
    for label, pat in DOMAIN_KW:
        if re.search(pat, blob, re.I):
            return label
    return "other"

def find_role_idx(sections, pattern):
    for i, s in enumerate(sections):
        if pattern.search(s): return i
    return None

def section_spans(body, sections):
    matches = list(SECTION_TITLES_RE.finditer(body))
    spans = []
    for i, _ in enumerate(sections):
        if i < len(matches): start = matches[i].start()
        elif spans: start = spans[-1][1]
        else: start = 0
        end = matches[i + 1].start() if (i + 1) < len(matches) else len(body)
        if start < 0: start = (spans[-1][1] if spans else 0)
        spans.append((start, end))
    return spans

def classify_bib_venue(field_blob):
    for venue, pat in VENUE_PATTERNS:
        if pat.search(field_blob): return venue
    return "other"

def scan_bib_venues(paper_dir):
    counts = {"NLP_conf": 0, "ML_conf": 0, "CV_conf": 0, "preprint": 0, "journal": 0, "other": 0}
    found_any = False
    macro_re = re.compile(r"@String\s*\{\s*(\w+)\s*=\s*\{([^}]*)\}\s*\}", re.I)
    field_re = re.compile(r"(?:journal|booktitle|bookTitle)\s*=\s*(?:\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}|([A-Za-z][\w\-]*))", re.S)
    for root, _, files in os.walk(paper_dir):
        for f in files:
            if not f.endswith(".bib"): continue
            # ponytail: skip bundled anthology bibs (>5 MB ≈ the entire ACL Anthology,
            # not the paper's own references). Including them absurdly skews per-paper
            # venue counts (one paper would claim ~100k citations). Mark found_any so the
            # paper is not miscounted as "no bib at all" — its other .bib files still count.
            try:
                if os.path.getsize(os.path.join(root, f)) > 5_000_000:
                    found_any = True
                    continue
            except OSError:
                continue
            try:
                with open(os.path.join(root, f), encoding="utf-8", errors="ignore") as fh:
                    txt = fh.read()
            except OSError: continue
            found_any = True
            macros = {k: v for k, v in macro_re.findall(txt)}
            for _key, blob in iter_bib_entries(txt):
                fm = field_re.search(blob)
                if fm:
                    v_in = fm.group(1); v_tok = fm.group(2)
                    if v_in is not None:
                        val = (v_in + " " + v_tok) if v_tok else v_in
                    elif v_tok:
                        val = macros.get(v_tok, "") + " " + v_tok
                    else: val = ""
                else:
                    # ponytail: no journal/booktitle field — skip. The previous fallback
                    # (blob[:60]) read title/author snippets ("author Dan Gusfield title
                    # Algorithms") and polluted the "other" bucket with non-venue text.
                    # These entries are valid citations but contribute nothing to venue
                    # classification; the \cite count metric is computed separately.
                    continue
                counts[classify_bib_venue(val if val else blob[:60])] += 1
    return counts, found_any

def extract_method_name(title, body):
    m = re.search(r"we\s+(?:propose|present|introduce|call)\s+(?:it\s+)?\\?(?:textbf|emph)?\s*\{?\s*([A-Z][A-Za-z0-9\-]{2,})", body)
    if m: return m.group(1)
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
    title = title_m.group(1).strip() if title_m else ""
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
        if i is None or i >= len(spans): return ""
        return body[spans[i][0]:spans[i][1]] if spans[i][0] >= 0 else ""
    intro_text = slice_idx(intro_idx)
    related_words = count_words(slice_idx(related_idx)) if related_idx is not None else 0
    # ponytail: method block = everything between Intro and the earliest of
    # {Experiments, Conclusion}. Anchored at intro_idx+1 (NOT related_idx) so layouts
    # like Intro -> Method -> Related -> Experiments (common in NLP) get the method block
    # right. Related Work interleaving inflates the block by related words (which have
    # few equations); acceptable for the corpus equation_count signal.
    m_start_idx = (intro_idx + 1) if intro_idx is not None else 0
    m_end_candidates = [i for i in (exp_idx, concl_idx)
                        if i is not None and i > m_start_idx]
    m_end_idx = min(m_end_candidates) if m_end_candidates else (len(sections) if m_start_idx < len(sections) else None)
    has_method_block = m_end_idx is not None and m_end_idx > m_start_idx and intro_idx is not None
    method_text = ""
    if has_method_block:
        m_start = spans[m_start_idx][0] if m_start_idx < len(spans) else 0
        m_end = spans[m_end_idx][0] if m_end_idx is not None and m_end_idx < len(spans) else len(body)
        method_text = body[m_start:m_end] if m_start >= 0 else ""
    intro_paras = len([p for p in re.split(r"\n\s*\n", intro_text) if p.strip()]) if intro_text else 0
    has_contrib = bool(CONTRIB_RE.search(intro_text)) if intro_text else False
    contrib_items = len(CONTRIB_ITEM_RE.findall(intro_text)) if intro_text else 0
    hook = None
    if intro_text:
        fs = first_sentence(intro_text)
        if fs.endswith("?"): hook = "question"
        elif re.search(r"\d+\s*%|\d+\s*(million|billion|thousand)|\b\d{4}\b", fs): hook = "statistic"
        elif fs.startswith('"') or fs.startswith("'"): hook = "quote"
        else: hook = "claim"
    opening_verb = None
    if abstract:
        m = OPENING_VERB_RE.search(abstract)
        if m: opening_verb = m.group(1).lower()
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
    # ponytail: single keyword classifier for both corpus and draft.
    domain = detect_domain(title, abstract or "")
    features = {
        "id": paper_id,
        "domain": domain,
        "domain_source": "keyword",
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

_ARXIV_ID_RE = re.compile(r"^\d{4}\.\d{4,5}$")

def main():
    os.makedirs(OUT, exist_ok=True)
    dirs = sorted(d for d in os.listdir(DATA)
                  if os.path.isdir(os.path.join(DATA, d)) and _ARXIV_ID_RE.match(d))
    n_ok = n_err = 0
    for d in dirs:
        out_path = os.path.join(OUT, d + ".json")
        if os.path.exists(out_path):
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