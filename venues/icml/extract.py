#!/usr/bin/env python3
# ponytail: deterministic per-paper feature extractor for ICML 2026 spotlight corpus.
# Adapted from CVPR extract.py (same LaTeX extractors, same partial-safe design).
# Two deltas vs CVPR:
#   1. Domain tagging: uses OpenReview primary_area (normalized to 10 buckets) for
#      corpus papers; falls back to keyword classifier matching the same 10 buckets
#      for drafts without an OpenReview area (e.g., user's own draft).
#   2. Citation venue patterns extended for ML conferences (NeurIPS, ICLR, COLT,
#      AISTATS, UAI, IJCAI, AAAI, KDD, COLM, EMNLP, ACL) — ML_conf is the dominant
#      family for ICML papers, CV_conf is now secondary.
import os, re, json, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "features")
PAPERS_JSON = os.path.join(DATA, "papers.json")

CITATION_RE = re.compile(r"\\(?:cite|citep|citet|citeauthor|citeyear|parencite|autocite)\b")
EQ_RE = re.compile(r"\\begin\{(?:equation|align|gather|multline|eqnarray)\*?\}")
FIG_RE = re.compile(r"\\begin\{figure\*?\}")
TBL_RE = re.compile(r"\\begin\{table\*?\}")
SECTION_RE = re.compile(r"\\section\*?\s*\{")
SECTION_TITLES_RE = re.compile(r"\\section\*?\s*\{([^}]*)\}")
ROLE_INTRO_RE = re.compile(r"intro", re.I)
ROLE_RELATED_RE = re.compile(r"\brelated\s+(?:works?|research|literature|studies)|prior\s+works?|previous\s+works?|background\s+and\s+related", re.I)
ROLE_EXP_RE = re.compile(r"experiment|evaluat|result|comparison", re.I)
ROLE_CONCL_RE = re.compile(r"conclu|discussion", re.I)
ABLATION_RE = re.compile(r"ablation", re.I)
SUBSECTION_RE = re.compile(r"\\subsection\*?\s*\{([^}]*)\}")
ABSTRACT_RE = re.compile(r"\\begin\{abstract\}\s*(.*?)\s*\\end\{abstract\}", re.S)
ABSTRACT_STOP_RE = re.compile(r"\\(?:section|subsection|input|include|begin\{document|chapter)\b")

# ponytail: 10-bucket ML domain vocabulary. Same labels for OpenReview-area mapping
# (AREA_TO_DOMAIN) and for keyword fallback (DOMAIN_KW). Keep in sync.
DOMAINS = ["llm", "generative", "vision", "rl", "theory", "social",
           "science_apps", "optimization", "probabilistic", "general_ml"]

# ponytail: normalize OpenReview primary_area ("top->sub" or "top") to one of DOMAINS.
# Conservative mapping: each top-level goes primarily to one bucket; a few sub-areas
# that are clearly a different bucket are split out.
AREA_TO_DOMAIN = [
    # specific sub-areas first (longer match wins via the loop)
    ("deep_learning->large_language_models", "llm"),
    ("deep_learning->generative_models_and_autoencoders", "generative"),
    ("deep_learning->foundation_models", "generative"),
    ("deep_learning->graph_neural_networks", "general_ml"),
    ("deep_learning->attention_mechanisms", "general_ml"),
    ("deep_learning->sequential_models_time_series", "general_ml"),
    ("deep_learning->algorithms", "general_ml"),
    ("deep_learning->theory", "theory"),
    ("deep_learning->robustness", "social"),
    ("deep_learning->selfsupervised_learning", "general_ml"),
    ("deep_learning->everything_else", "general_ml"),
    ("deep_learning->other_representation_learning", "general_ml"),
    ("deep_learning->diffusion_models", "generative"),
    ("deep_learning", "general_ml"),
    ("applications->computer_vision", "vision"),
    ("applications->language_speech_and_dialog", "llm"),
    ("applications->robotics", "science_apps"),
    ("applications->chemistry_physics_and_earth_sciences", "science_apps"),
    ("applications->neuroscience_cognitive_science", "science_apps"),
    ("applications->health_medicine", "science_apps"),
    ("applications->time_series", "general_ml"),
    ("applications->everything_else", "science_apps"),
    ("applications", "science_apps"),
    ("social_aspects->accountability_transparency_and_interpretability", "social"),
    ("social_aspects->alignment", "social"),
    ("social_aspects->safety", "social"),
    ("social_aspects->privacy", "social"),
    ("social_aspects->security", "social"),
    ("social_aspects->fairness", "social"),
    ("social_aspects->robustness", "social"),
    ("social_aspects->everything_else", "social"),
    ("social_aspects", "social"),
    ("theory->learning_theory", "theory"),
    ("theory->deep_learning", "theory"),
    ("theory->game_theory", "theory"),
    ("theory->optimization", "optimization"),
    ("theory->online_learning_and_bandits", "theory"),
    ("theory->reinforcement_learning_and_planning", "rl"),
    ("theory->probabilistic_methods", "probabilistic"),
    ("theory->domain_adaptation_and_transfer_learning", "general_ml"),
    ("theory->everything_else", "theory"),
    ("theory", "theory"),
    ("reinforcement_learning->deep_rl", "rl"),
    ("reinforcement_learning->multiagent", "rl"),
    ("reinforcement_learning->batchoffline", "rl"),
    ("reinforcement_learning->policy_search", "rl"),
    ("reinforcement_learning->inverse", "rl"),
    ("reinforcement_learning->online", "rl"),
    ("reinforcement_learning->planning", "rl"),
    ("reinforcement_learning", "rl"),
    ("optimization->discrete_and_combinatorial_optimization", "optimization"),
    ("optimization->nonconvex", "optimization"),
    ("optimization->convex", "optimization"),
    ("optimization", "optimization"),
    ("probabilistic_methods->monte_carlo_and_sampling_methods", "probabilistic"),
    ("probabilistic_methods->bayesian_models_and_methods", "probabilistic"),
    ("probabilistic_methods->variational_inference", "probabilistic"),
    ("probabilistic_methods->structure_learning", "probabilistic"),
    ("probabilistic_methods->everything_else", "probabilistic"),
    ("probabilistic_methods", "probabilistic"),
    ("general_machine_learning->evaluation", "general_ml"),
    ("general_machine_learning->causality", "general_ml"),
    ("general_machine_learning->representation_learning", "general_ml"),
    ("general_machine_learning->transfer_multitask_and_metalearning", "general_ml"),
    ("general_machine_learning->hardware_and_software", "general_ml"),
    ("general_machine_learning->scalable_algorithms", "general_ml"),
    ("general_machine_learning->clustering", "general_ml"),
    ("general_machine_learning->kernel_methods", "general_ml"),
    ("general_machine_learning->unsupervised_and_semisupervised_learning", "general_ml"),
    ("general_machine_learning->online_learning_active_learning_and_bandits", "general_ml"),
    ("general_machine_learning->sequential_network_and_time_series_modeling", "general_ml"),
    ("general_machine_learning->everything_else", "general_ml"),
    ("general_machine_learning", "general_ml"),
]

# ponytail: keyword fallback (used when no OpenReview primary_area; e.g., user drafts).
# Same 10 bucket labels as AREA_TO_DOMAIN so the analyzer compares against consistent
# per-domain medians no matter which path produced the tag.
DOMAIN_KW = [
    ("llm", r"\b(large\s+language|LLM|GPT\b|reasoning\s+model|instruction\s+tun|prompt)"
            r"|\btransformer\b(?# only when context has language)"),
    ("generative", r"\b(diffusion|VAE|variational\s+auto|generative\s+model|synthesi\w+|text-to-)\b"),
    ("vision", r"\b(image\s+classif|segmentation|object\s+detection|optical\s+flow|CLIP\b|video\s+classif)\b"),
    ("rl", r"\b(reinforcement|policy\s+gradient|RL\b|MDP\b|reward|bandit|agent)\b"),
    ("theory", r"\b(theorem|lemma|regret\s+bound|sample\s+complexity|PAC\b|learnability)\b"),
    ("social", r"\b(alignment|safety|fairness|interpretability|privacy|adversarial\s+attack)\b"),
    ("science_apps", r"\b(robot|chemistry|molecule|protein|drug|health|clinical|neuroscience)\b"),
    ("optimization", r"\b(optimization|convex|gradient\s+descent|convergence\s+rate|nonconvex)\b"),
    ("probabilistic", r"\b(Bayesian|MCMC|Monte\s+Carlo|posterior\s+infer|probabilistic\s+model)\b"),
    ("general_ml", r"\b(representation\s+learning|self-supervised|meta-?learn|transfer\s+learn|"
                   r"deep\s+learning|neural\s+net|training\s+method)\b"),
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
BIB_ENTRY_RE = re.compile(r"@\w+\s*\{([^,]+),\s*(.*?)\n\}", re.S)
BIB_FIELD_RE = re.compile(r"(author|title|journal|booktitle|bookTitle|publisher)\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", re.S)
# ponytail: ICML papers cite ML venues heavily. CV_conf kept (NeurIPS/CVPR cross-listings,
# Robotics+Vision papers, papers-with-code bias) but ML_conf widened to the academic ML family.
VENUE_PATTERNS = [
    # ponytail: ML_conf matches acronym + spelled-out forms for the academic ML family.
    # Spelled-out variants common in ICML bibs ("Advances in Neural Information Processing
    # Systems", "Conference on Uncertainty in Artificial Intelligence", "International
    # Conference on Machine Learning").
    ("ML_conf", re.compile(
        r"\b(ICML|ICLR|NeurIPS|NIPS|COLM|COLT|AISTATS|UAI|IJCAI|AAAI|KDD|WWW|SIGIR|SODA|STOC|FOCS)\b"
        r"|Int(ernational)?\s+Conf\w*\s+(on\s+)?(?:Machine\s+Learn|Mach\.\s*Learn|Learn\.\s*Represent|Learning\s+Representations|Learn\.\s*The|AI\s+and\s+Statistic|AI\s+Stat)"
        r"|Conf\w*\s+on\s+(?:Neural\s+Information|Uncertainty\s+(?:in\s+)?Artificial\s+Intelligence|Learning\s+Theory|Uncertainly\s+in\s+AI)"
        r"|Adv\w*\s+in\s+Neural\s+Information\s+Process\w*\s+Systems"
        r"|Int\.\s+Conf\.\s+(?:Mach\.\s*Learn|Learn\.\s*Represent|Learn\.\s*The|AI\s+Stat)"
        r"|Int\.\s+Joint\s+Conf\.\s+AI"
        r"|AAAI\s+Conf"
        r"|ACM\s+SIGKDD|ACM\s+(?:SIGKDD|Web\s+Search|STOC|SODA)"
        r"|ACL\b|EMNLP\b|NAACL\b"
        r"|Empirical\s+Methods\s+in\s+Natural\s+Language"
        r"|Annual\s+(?:Meeting\s+of\s+(?:the\s+)?Association\s+for\s+)?Computational?\s+Linguistics",
        re.I)),
    ("CV_conf", re.compile(
        r"\b(CVPR|ICCV|ECCV|ACCV|CVPRW|WACV|BMVC)\b"
        r"|Comput\.\s*Vis\.\s*Pattern\s*Recog"
        r"|Conf\.\s*Comput\.\s*Vis"
        r"|Int\.\s*Conf\.\s*on\s*Comput\.\s*Vis"
        r"|European\s*Conf\.\s*Comput\.\s*Vis"
        r"|Computer\s*Vision\s*and\s*Pattern\s*Recogn", re.I)),
    ("preprint", re.compile(r"\barxiv\b|OpenReview\b|CoRR\b", re.I)),
    # ponytail: journals — IEEE/ACM family + ML/stats journals heavy in ICML citations.
    ("journal", re.compile(
        r"\b(IEEE|ACM)\b|TPAMI|IJCV|JMLR|TACL|TIT\b|TIM\b|TIP\b|TMLR\b"
        r"|Trans\.\s*Pattern\s*Anal"
        r"|J\.\s*Mach\.\s*Learn\.\s*Res"
        r"|Trans\.\s*Image\s*Process"
        r"|Pattern\s*Anal\.\s*Mach\.\s*Intell"
        r"|Int\.\s*J\.\s*Comput\.\s*Vis"
        r"|Transactions\s+(?:on\s+)?(?:Machine\s+Learning\s+Research|Pattern\s+Analysis|Information\s+Theory)"
        r"|Nature|Science|PNAS\b"
        # stats journals heavy in ICML probabilistic papers
        r"|Bernoulli\b|Biometrika\b|J\.\s*Roy\.\s*Statist\.\s*Soc|Bayesian\s+Analysis"
        r"|Journal\s+of\s+(?:the\s+)?(?:American\s+Statistical\s+Assoc|Royal\s+Statistical\s+SOC|Machine\s+Learning\s+Research)"
        r"|Ann\.\s+Appl\.\s+Probab|Annals\s+of\s+Applied\s+Probability"
        r"|Statistics\s+and\s+Computing"
        r"|J\.\s+Chem\.\s+Phys|Journal\s+of\s+Chemical\s+Physics",
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
    cands = []
    for root, _, files in os.walk(paper_dir):
        depth = root[len(paper_dir):].count(os.sep)
        if depth > 3: continue
        for f in files:
            if f.endswith(".tex"): cands.append(os.path.join(root, f))
    def root_score(p):
        nm = os.path.basename(p).lower()
        pref = 0
        for k, w in [("main.tex", -3), ("arxiv.tex", -3), ("paper.tex", -3),
                     ("icml_main.tex", -3), ("icml.tex", -3),
                     ("main", -2), ("icml", -2)]:
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

def detect_domain_keywords(title, abstract):
    # ponytail: keyword fallback matching the 10-bucket vocabulary.
    # Try title first (most discriminating), then abstract.
    for src in (title or "", abstract or ""):
        for label, pat in DOMAIN_KW:
            if re.search(pat, src, re.I):
                return label
    return "general_ml"

def map_primary_area(area):
    # ponytail: area is "top->sub" or "top"; first matching entry wins (specific sub-areas first).
    if not area: return None
    a = area.strip().lower()
    for key, dom in AREA_TO_DOMAIN:
        if a == key.lower() or a.startswith(key.lower()):
            return dom
    return "general_ml"

_PAPERS_LOOKUP = None  # cached arxiv_id -> primary_area
def _load_papers_lookup():
    # ponytail: feature paper_id == arxiv_id (dir name). papers.json keys by OpenReview id.
    # Join through arxiv_matches.json (paper_id <-> arxiv_id) to map arxiv_id -> primary_area.
    global _PAPERS_LOOKUP
    if _PAPERS_LOOKUP is None:
        _PAPERS_LOOKUP = {}
        try:
            papers = {p["id"]: p.get("primary_area") for p in json.load(open(PAPERS_JSON))}
            matches = json.load(open(os.path.join(DATA, "arxiv_matches.json")))
            for m in matches:
                aid = m.get("arxiv_id"); orid = m.get("paper_id")
                if aid and orid and orid in papers:
                    _PAPERS_LOOKUP[aid] = papers[orid]
        except (OSError, json.JSONDecodeError):
            pass
    return _PAPERS_LOOKUP

def detect_domain_for_paper(paper_id, title, abstract):
    # ponytail: corpus papers have OpenReview primary_area; drafts don't.
    area = _load_papers_lookup().get(paper_id)
    if area:
        return map_primary_area(area)
    return detect_domain_keywords(title, abstract)

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
    counts = {"CV_conf": 0, "ML_conf": 0, "preprint": 0, "journal": 0, "other": 0}
    found_any = False
    macro_re = re.compile(r"@String\s*\{\s*(\w+)\s*=\s*\{([^}]*)\}\s*\}", re.I)
    field_re = re.compile(r"(?:journal|booktitle|bookTitle)\s*=\s*(?:\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}|([A-Za-z][\w\-]*))", re.S)
    for root, _, files in os.walk(paper_dir):
        for f in files:
            if not f.endswith(".bib"): continue
            try:
                with open(os.path.join(root, f), encoding="utf-8", errors="ignore") as fh:
                    txt = fh.read()
            except OSError: continue
            found_any = True
            macros = {k: v for k, v in macro_re.findall(txt)}
            for m in BIB_ENTRY_RE.finditer(txt):
                blob = m.group(2)
                fm = field_re.search(blob)
                if fm:
                    v_in = fm.group(1); v_tok = fm.group(2)
                    if v_in is not None:
                        val = (v_in + " " + v_tok) if v_tok else v_in
                    elif v_tok:
                        val = macros.get(v_tok, "") + " " + v_tok
                    else: val = ""
                else:
                    val = blob[:60]
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
    # {Experiments, Conclusion}. Anchored at intro_idx (NOT related_idx) so layouts
    # like Intro -> Method -> Related -> Experiments (common in ICML) get the method
    # block right. Related Work interleaving inflates the block by related words
    # (which have few equations); acceptable for the corpus equation_count signal.
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
    # ponytail: domain is OpenReview primary_area bucket when available (corpus),
    # else keyword fallback. Both produce the same 10-bucket vocabulary.
    domain = detect_domain_for_paper(paper_id, title, abstract or "")
    domain_src = "openreview_area" if _load_papers_lookup().get(paper_id) else "keyword"
    features = {
        "id": paper_id,
        "domain": domain,
        "domain_source": domain_src,
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
    # ponytail: only process arxiv-id-shaped dirs; skip reviews/, papers.json, etc.
    dirs = sorted(d for d in os.listdir(DATA)
                  if os.path.isdir(os.path.join(DATA, d)) and _ARXIV_ID_RE.match(d))
    n_ok = n_err = 0
    for d in dirs:
        out_path = os.path.join(OUT, d + ".json")
        if os.path.exists(out_path):
            n_ok += 1; continue
        try:
            feats = extract_features(d, os.path.join(DATA, d))
            with open(out_path, "w") as fh: json.dump(feats, fh, indent=2)
            if feats.get("error"):
                n_err += 1
                print(f"[err] {d}: {feats['error']}", file=sys.stderr)
            else:
                n_ok += 1
                print(f"[ok] {d}: domain={feats['domain']}({feats['domain_source'][0]}) "
                      f"secs={feats['structure']['section_count']} "
                      f"abs_s={feats['abstract']['sentences']}", file=sys.stderr)
        except Exception as e:
            n_err += 1
            print(f"[exc] {d}: {e}", file=sys.stderr)
    print(f"[done] ok={n_ok} err={n_err} out={OUT}", file=sys.stderr)

if __name__ == "__main__":
    main()