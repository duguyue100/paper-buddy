# paper-buddy

The buddy you always wanted when writing papers.

Two [opencode](https://opencode.ai) skills that give a grad student (possibly solo,
no supervisor around) the kind of grounded, corpus-backed feedback a senior
co-author would give — instead of generic "make the abstract clearer" advice.

- **`paper-style`** — measures your LaTeX draft against aggregated style facts
  extracted from a corpus of recent accepted papers at that venue. Reports
  "your abstract is 14 sentences; the corpus median is 7 — you're likely
  spilling method detail into the abstract".
- **`paper-critic`** — reviews your draft section-by-section like a senior
  advisor / reviewer: finds logical gaps, unsupported claims, missing
  baselines/ablations, claim-to-evidence mismatch. For ICML the critique
  checklist is *review-derived* — mined from 2068 OpenReview reviews of the
  venue's accepted papers — so the critic asks the same questions actual
  reviewers at that venue ask.

Both skills are deterministic at runtime: a companion Python script
(`analyze.py` / `inspect.py`) measures the draft with the same extractor that
produced the corpus stats, and the LLM only narrates the numbers. No invented
feedback.

This repo is intentionally library-free at runtime — the analyzer/inspector use
only the Python standard library. The heavyweight corpus build (scraping,
arXiv downloads, feature extraction, review mining, aggregation) runs once,
offline, and the resulting reference files (`*_stats.json`, `*_style.md`,
`*_expectations.md`, `review_patterns.md`) are committed so skill users do not
need to re-run it.

## Supported venues

| Venue | Corpus | Critic checklist source |
|---|---|---|
| **CVPR 2026** | 106 accepted oral papers (top ~2% of submissions) — LaTeX sources scraped from CVPR open access | Hand-authored, domain-neutral advisor questions |
| **ICML 2026** | 303 accepted spotlight papers — LaTeX sources matched on arXiv (title + author surname verified) | **Review-derived**: mined from 2068 OpenReview reviews of 536 spotlights |
| **ACL 2026** | 267 accepted oral papers — LaTeX sources matched on arXiv from the 478-paper oral list (title + author surname verified) | Hand-authored, domain-neutral advisor questions (ACL has no public reviews) |

Each venue lives in its own directory (`venues/cvpr/`, `venues/icml/`,
`venues/acl/`) with two self-contained skills under `skills/paper-style/` and
`skills/paper-critic/`. Adding a new venue (ICLR, NeurIPS, EMNLP, …) is a matter
of copying the closest existing pipeline and re-pointing the scraper; see
[*Reproducing the corpus*](#reproducing-the-corpus).

## How to use

### 1. Install the skills

The skills are plain directories with a `SKILL.md`. Copy or symlink each skill
directory into your opencode skills config so opencode picks it up:

```bash
# pick the venue(s) you want
cp -r venues/cvpr/skills/paper-style    ~/.config/opencode/skills/paper-style-cvpr
cp -r venues/cvpr/skills/paper-critic   ~/.config/opencode/skills/paper-critic-cvpr
cp -r venues/icml/skills/paper-style    ~/.config/opencode/skills/paper-style-icml
cp -r venues/icml/skills/paper-critic   ~/.config/opencode/skills/paper-critic-icml
cp -r venues/acl/skills/paper-style     ~/.config/opencode/skills/paper-style-acl
cp -r venues/acl/skills/paper-critic    ~/.config/opencode/skills/paper-critic-acl
```

> The skill `name:` field in each `SKILL.md` is `paper-style` / `paper-critic`.
> If you install both venues side-by-side, either rename the directory or edit
> the `name:`/`description:` in `SKILL.md` to disambiguate (e.g.
> `paper-style-cvpr`). Only the matching skill will trigger off your wording.

### 2. Invoke in an opencode chat

Open a chat in a project that contains your LaTeX draft and just say what you
want:

```
check my paper style at /path/to/draft/
```
```
critique the method section of my draft at /path/to/draft/main.tex
```
```
is this ICML-shaped? /paper-style
```

The skill will ask for the draft path if you don't give one, run the
deterministic analyzer/inspector, read the reference files, and narrate the
findings as a short report with a prioritized fix list. Partial drafts are
fine — the scripts handle missing sections gracefully.

### Runtime requirements

- Python 3.10+ on your `PATH` (the runtime scripts are stdlib-only — no
  installs needed for *using* the skills).
- The committed `reference/` files (`*_stats.json`, `*_style.md`,
  `*_expectations.md`, `review_patterns.md`) ship with the skills, so using
  the skills requires **zero** network access or corpus rebuild.

## Key findings

### Style facts — CVPR vs ICML vs ACL

Numbers below are corpus **medians** with the interquartile band `[P25–P75]`,
computed by `aggregate.py` over each venue's feature set. The runtime
`paper-style` skill compares your draft to exactly these numbers.

| Field | CVPR 2026 (n=106) | ICML 2026 (n=303) | ACL 2026 (n=267) |
|---|---|---|---|
| Abstract — sentences | 8 [7–9] | 7 [6–8] | 7 [6–8] |
| Abstract — words | 169 [148–194] | 161 [144–185] | 157 [140–178] |
| Intro — paragraphs | 8 [7–11] | 9 [7–12] | 8 [7–11] |
| Related work — words | 393 [333–497] | 347 [264–465] | 298 [223–416] |
| Method — equations | 11 [6–16] | 17 [7–41] | 4 [0–8] |
| Method — figures | 2 [1–3] | 1 [0–2] | 1 [0–2] |
| Experiments — tables | 4 [2–7] | 5 [2–10] | 8 [4–12] |
| Experiments — ablation mentions | 7 [2–11] | 4 [0–10] | 4 [0–10] |
| Experiments — SOTA mentions | 10 [7–17] | 8 [4–13] | 9 [4–14] |
| Body — words | 5,282 [4,246–6,445] | 8,818 [6,967–11,202] | 6,269 [5,128–7,936] |
| Citations — total | 77 [56–98] | 60 [46–83] | 52 [41–68] |
| Has explicit Related Work section | 96% | 82% | 91% |
| Has explicit Ablation heading | 66% | 43% | 44% |
| Has Conclusion section | 96% | 86% | 97% |
| Has a contribution list in intro | 44% | 36% | 41% |
| Anchor-venue cite share (per-paper median) | CV-family 23% | ML-family 26% | NLP-family 8% |

A few patterns jump out:

- **ICML papers are denser in words and equations, lighter on citations.**
  ICML bodies median ~8.8k words vs CVPR's 5.3k, and ICML methods carry a
  median of 17 equations vs CVPR's 11 — but ICML citations are *fewer* (60 vs
  77). Reviewers expect more formal apparatus per claim at ICML.
- **ICML relies far less on explicit "Related Work" sections.** Only 82% of
  ICML spotlights have one (vs 96% of CVPR orals) — many ICML papers fold
  related work into the intro. The `paper-style` skill flags a missing Related
  Work section as a *question*, not a defect, for ICML.
- **Ablation practice differs sharply.** 66% of CVPR orals have an explicit
  ablation heading (median 7 ablation mentions); only 43% of ICML spotlights
  and 44% of ACL orals do (median 4 each). ICML reviewers more often ask for
  ablations in review than they find them in the paper — the #3 review pattern
  at ICML is "missing / incomplete ablation study" (3% of reviews). ACL papers
  typically isolate design choices under an "Analysis" heading instead; the
  ACL `inspect.py` checks for *both* Ablation and Analysis headings so an
  Analysis-led paper is not falsely flagged.
- **ACL methods are equation-light and table-heavy.** ACL methods carry a
  median of just 4 equation environments (vs CVPR 11, ICML 17) — many ACL
  methods are prompt-based or pipeline-based, and parsing papers have *zero*.
  But ACL experiments show a median of 8 tables (vs CVPR 4, ICML 5). The
  `paper-style` skill marks `method.equation_count` domain-sensitive and
  flags table counts >12 or <4 as worth justifying.
- **Citation venue mix is a strong venue-anchoring signal.** CVPR papers cite
  vision-family venues (CVPR/ICCV/ECCV) at a per-paper median of **23%**; ICML
  papers cite ML-family venues (ICML/ICLR/NeurIPS/COLT/AISTATS/AAAI/IJCAI/KDD/
  UAI/…) at a per-paper median of **26%** — and cite vision venues at a median
  of **0%**. ACL papers cite NLP-family venues (ACL/EMNLP/NAACL/COLING/TACL/
  Findings) at a per-paper median of just **8%** — *lower than expected*
  because modern ACL papers lean heavily on arXiv preprints (~32%) and ML
  conferences (~20%). A draft with NLP-family share near 0 is flagged as
  possible "style drift toward ML conferences" — but a 2-3% share is normal,
  not a defect.

### Per-domain equations (ICML)

ICML is broad enough that one median doesn't fit all sub-fields. The
extractor tags each paper to one of 10 domain buckets (from OpenReview's
`primary_area`, with a keyword fallback for non-corpus drafts) and the
aggregator reports per-domain medians for domain-sensitive fields. Equation
count is the clearest example:

| Domain | Equations (median) | n |
|---|---|---|
| theory | 66 | 31 |
| optimization | 38 | 10 |
| probabilistic | 39 | 13 |
| generative | 25.5 | 24 |
| rl | 21.5 | 24 |
| science_apps | 16 | 31 |
| social | 16 | 37 |
| general_ml | 13 | 54 |
| vision | 10 | 17 |
| llm | 8.5 | 62 |

The `paper-style` skill uses per-domain medians for `domain-sensitive` fields
(abstract length, equations, body words) so a theory paper with 60 equations
isn't flagged against the LLM-bucket median of 8.5.

### Per-domain equations (ACL)

ACL has no OpenReview `primary_area` so domain tagging is keyword-only over
title+abstract, mapped to 10 NLP-appropriate buckets inspired by ACL's official
submission tracks. The keyword tagger is noisier than ICML's area-based path
(~67% of papers land in `llm_reasoning`), so per-domain medians are best read
as directional, not authoritative. Equation count again shows the clearest
domain spread:

| Domain | Equations (median) | n |
|---|---|---|
| efficiency | 8 | 5 |
| other | 6.5 | 22 |
| generation | 4 | 36 |
| llm_reasoning | 3 | 180 |
| multimodal | 2 | 11 |
| parsing_linguistic | 0 | 7 |

A parsing paper with 0 equations is normal; an efficiency paper with 0 is a
question. The skill flags `method.equation_count` as domain-sensitive and
prompts for a domain justification rather than a global-median violation.

### Review-derived critic patterns (ICML only)

`mine_reviews.py` regex-mines the 2068 OpenReview reviews of ICML 2026
spotlights for 15 recurring complaint patterns (each counted at most once per
review to avoid double-counting), then writes anonymized verbatim reviewer
quotes for each pattern into `review_patterns.md`. The top patterns — i.e.
what ICML reviewers *actually* complain about, in descending frequency:

| % of reviews | Pattern |
|---|---|
| 24% | Writing / clarity issues |
| 24% | Limited / insufficient experiments or scale |
| 5%  | Technical / correctness errors |
| 3%  | Weak / missing / outdated baselines |
| 3%  | Compute / efficiency concerns |
| 3%  | Missing / incomplete ablation study |
| 2%  | Limited / incremental novelty |
| 2%  | Limited / narrow datasets or benchmarks |
| 1%  | Restrictive / unrealistic assumptions |
| 1%  | Reproducibility / code missing |

The `paper-critic` skill uses this list (not a hand-authored checklist) as its
critique agenda, and `inspect.py` re-scans the draft's section text against the
same regex dictionary so the critic can quote the exact suspicious sentence
("you say 'outperforms all baselines' but never name a baseline by citation —
reviewers raised 'weak baselines' in 3% of ICML reviews").

CVPR and ACL have no public review corpus (CVPR has no open reviews; ACL doesn't
publish on OpenReview), so those two critics use a hand-authored domain-neutral
`critique_checklist.md` instead. The ACL checklist is NLP-tuned (LLM-era
baselines, prompt-template disclosure, annotation protocols for resource
papers, analysis-vs-ablation heading tolerance).

## Project structure

```
main/
├── README.md                      ← you are here
├── venues/
│   ├── cvpr/                      ← CVPR 2026 pipeline (complete)
│   │   ├── scrape_orals.py        ← scrape CVPR open-access paper list + sources
│   │   ├── extract.py             ← per-paper feature extractor
│   │   ├── aggregate.py           ← fold features → skill reference files
│   │   └── skills/
│   │       ├── paper-style/       ← SKILL.md + scripts/analyze.py + reference/
│   │       └── paper-critic/      ← SKILL.md + scripts/inspect.py + reference/
│   ├── icml/                      ← ICML 2026 pipeline (complete)
│   │   ├── scrape_papers.py       ← OpenReview spotlight metadata
│   │   ├── match_arxiv.py         ← match papers to arXiv (title + authors)
│   │   ├── download_sources.py    ← pull arXiv LaTeX tarballs
│   │   ├── scrape_reviews.py      ← OpenReview reviews/rebuttals/decisions
│   │   ├── extract.py             ← per-paper feature extractor (+ domain tagging)
│   │   ├── mine_reviews.py        ← mine reviewer complaint patterns
│   │   ├── aggregate.py           ← fold features + patterns → skill reference files
│   │   ├── .env                  ← OpenReview EMAIL/PASSWORD (gitignored, NOT committed)
│   │   └── skills/
│   │       ├── paper-style/       ← SKILL.md + scripts/analyze.py + reference/
│   │       └── paper-critic/      ← SKILL.md + scripts/inspect.py + reference/
│   └── acl/                       ← ACL 2026 pipeline (complete)
│       ├── scrape_arxiv.py        ← match 478 oral papers to arXiv + download tarballs (one shot)
│       ├── extract.py             ← per-paper feature extractor (NLP venues, balanced-brace bib scanner)
│       ├── aggregate.py           ← fold features → skill reference files
│       └── skills/
│           ├── paper-style/       ← SKILL.md + scripts/analyze.py + reference/
│           └── paper-critic/      ← SKILL.md + scripts/inspect.py + reference/
└── (data/ and features/ are generated per-venue, gitignored — not committed)
```

Inside each skill directory:

```
skills/paper-style/
├── SKILL.md                       ← opencode skill definition (frontmatter + workflow)
├── scripts/
│   └── analyze.py                ← runtime: measure a draft (imports venue's extract.py)
└── reference/
    ├── <venue>_style.md           ← human-readable aggregated style facts
    └── <venue>_stats.json         ← machine-queryable medians / distributions

skills/paper-critic/
├── SKILL.md
├── scripts/
│   └── inspect.py                 ← runtime: extract sections + critique signals
└── reference/
    ├── <venue>_expectations.md    ← compact corpus medians for the critic
    ├── critique_checklist.md      ← CVPR & ACL: hand-authored advisor questions
    └── review_patterns.md         ← ICML only: mined reviewer complaint patterns
```

> **What's committed vs generated.** Skills (SKILL.md + scripts) and reference
> files are committed, so you can use the skills with zero rebuild. The raw
> corpus (`data/` — scraped paper metadata, arXiv tarballs, review JSON) and
> per-paper features (`features/`) are *not* committed — they're large and
> reproducible from the scripts. `.gitignore` excludes them, plus `.env`,
> `__pycache__/`, `.mypy_cache/`.

## Reproducing the corpus

You only need this if you want to rebuild the reference files (e.g. for a new
year's papers, a new venue, or after tweaking the extractor). Using the skills
does **not** require any of this — the reference files are committed.

### Environment

Python 3.10+ in a uv venv works well. The runtime skills are stdlib-only; only
the corpus-build scripts need third-party packages, and only for the ICML
OpenReview scraping:

```bash
# from the repo root
uv venv .venv --python 3.12
source .venv/bin/activate
pip install openreview-py python-dotenv   # only needed for ICML scraping
```

For CVPR, the scraper uses only `urllib` + `xml` from the stdlib — no extra
deps.

### CVPR 2026 pipeline

```bash
cd venues/cvpr
# 1. Scrape the CVPR open-access oral paper list + LaTeX sources → data/
python scrape_orals.py
# 2. Extract per-paper features → features/*.json
python extract.py
# 3. Aggregate features → skills/paper-style/reference/, skills/paper-critic/reference/
python aggregate.py
```

CVPR's `critique_checklist.md` (hand-authored) is committed directly — no
build step.

### ICML 2026 pipeline

```bash
cd venues/icml
# OpenReview scraping needs credentials — create a .env file with:
#     EMAIL=you@example.edu
#     PASSWORD=...
# (.env is gitignored; .env is NOT committed.)

# 1. Scrape OpenReview spotlight metadata          → data/papers.json  (536 papers)
python scrape_papers.py
# 2. Match papers to arXiv by title + author       → data/arxiv_matches.json  (303 matched)
python match_arxiv.py
# 3. Download LaTeX tarballs from arXiv            → data/<arxiv_id>/  (303 dirs, ~1.8 GB)
python download_sources.py
# 4. Scrape reviews/rebuttals/decisions             → data/reviews/<paper_id>.json
python scrape_reviews.py
# 5. Extract per-paper features                     → features/*.json  (303 features)
python extract.py
# 6. Mine reviewer complaint patterns               → data/review_patterns.json
python mine_reviews.py        # also writes skills/paper-critic/reference/review_patterns.md
# 7. Aggregate features + patterns → skills/*/reference/
python aggregate.py
```

`aggregate.py` is idempotent — safe to re-run after editing any upstream
script. It writes `icml_stats.json`, `icml_style.md` (paper-style) and
`icml_expectations.md` (paper-critic).

> **OpenReview rate limit.** The OpenReview API allows 3 requests per 25
> seconds on login; `openreview-py` handles pagination via `get_all_notes`,
> so the scrapers are mostly batched. Expect `scrape_reviews.py` to take a
> few minutes.
>
> **arXiv matching.** `match_arxiv.py` uses strict normalized-title
> matching plus an author-surname confirmation; 303/536 (56.5%) of
> spotlights matched. The unmatched papers are mostly OpenReview-only
> submissions without an arXiv preprint — that's expected. Only the 303
> matched papers contribute LaTeX sources to the corpus.

### ACL 2026 pipeline

ACL has no OpenReview (no public reviews either), so the pipeline is the
simplest of the three: one script matches the venue's oral paper list to
arXiv and downloads LaTeX tarballs, then the same extract/aggregate flow. No
review mining step. Python stdlib only — no extra deps.

```bash
cd venues/acl
# 1. Match 478 oral papers to arXiv + download tarballs  → data/arxiv_matches.json, data/<arxiv_id>/  (267 matched, ~3.2 MB)
python scrape_arxiv.py
# 2. Extract per-paper features                          → features/*.json  (267 features)
python extract.py
# 3. Aggregate features → skills/*/reference/
python aggregate.py        # writes acl_stats.json, acl_style.md, acl_expectations.md
```

ACL's `critique_checklist.md` (hand-authored, NLP-tuned) is committed
directly — no build step.

> **arXiv matching (ACL).** `scrape_arxiv.py` uses the same strict
> normalized-title equality + author-surname confirmation as ICML's
> `match_arxiv.py`. 267/478 (55.9%) of ACL orals matched — the unmatched
> ones are venue-only submissions without an arXiv preprint; that's
> expected for ACL (a sizeable fraction of NLP work, especially resources /
> Dataset papers, doesn't go through arXiv).
>
> **Large bundled bibtex (ACL).** A handful of ACL LaTeX tarballs bundle
> the entire 30–46 MB ACL Anthology `*.bib` file. `extract.py` uses a
> balanced-brace walker instead of the lazy-regex scanner from CVPR/ICML
> (which catastrophically backtracks on those files) and skips `*.bib`
> files >5 MB so they don't pollute per-paper venue distributions.

### Adding a new venue

The pipeline you start from depends on what the venue publishes:

- **OpenReview-based venue with public reviews** (ICLR, NeurIPS, …) → start
  from the **ICML** pipeline. Edit the invitation ID in `scrape_papers.py`
  and `scrape_reviews.py` (search for `ICML` / `2026`); repoint
  `AREA_TO_DOMAIN` in `extract.py` if the venue uses different
  `primary_area` strings (or drop domain tagging if it doesn't tag areas);
  re-run the 7 ICML steps; rename output files (`iclr_stats.json`,
  `iclr_style.md`, `iclr_expectations.md`, `review_patterns.md`, …) by
  editing the few hardcoded strings in `aggregate.py` / `mine_reviews.py`;
  edit the two `SKILL.md` frontmatter strings (name + description) so
  opencode triggers off the new venue's wording.
- **Open-access proceedings page, no OpenReview** (ICCV, ECCV, WACV, …) →
  start from the **CVPR** pipeline. Rewrite `scrape_orals.py` to hit the
  venue's proceedings page; re-run the 3 CVPR steps.
- **arXiv-only matching (no OpenReview, no open-access proceedings)** (EMNLP,
  NAACL, COLING if they don't expose per-paper LaTeX at the time of building)
  → start from the **ACL** pipeline, which is the leanest of the three:
  `scrape_arxiv.py` does match+download in one shot, no extra deps. Edit the
  oral paper list input and the arXiv search helper, then run the 3 ACL
  steps. The ACL `extract.py` also has the most robust bibtex scanner
  (balanced-brace walker + >5 MB skip) — copy that file wholesale rather
  than CVPR/ICML's older regex scanner.

## Design decisions

A few worth knowing about, since they shape what the skills do (and don't):

- **Deterministic analysis, not "ask the LLM".** Every measurement at runtime
  comes from a Python script using the same extractor that built the corpus
  stats. The LLM narrates; it does not measure, count, or grade. This is what
  makes the feedback trustworthy — the corpus numbers are real, not
  generated.
- **Two-skill split.** `paper-style` is corpus-grounded measurement (a paper
  out of shape vs the corpus). `paper-critic` is professor reasoning (is the
  argument sound). Style and substance are different questions and the user
  often wants only one — splitting them keeps each report focused.
- **Per-domain medians for domain-sensitive fields.** A theory paper with 60
  equations is normal; an LLM paper with 60 equations is not. The aggregator
  computes per-domain medians for fields where the domain drives the value
  (equations, abstract length, body words). The runtime report prints a
  `domain-sensitive-deviation` status that asks the author to justify against
  their sub-field's median rather than the global one. ICML has 10 buckets
  driven by OpenReview `primary_area`; ACL has 10 NLP-appropriate buckets
  driven by a keyword classifier over title+abstract (noisier — a ceiling we
  note, upgrade to embeddings if granularity matters); CVPR is small enough
  (n=106 orals) that we use global medians only.
- **Partial-draft tolerance.** Grad students write papers one section at a
  time. The extractor handles missing sections gracefully (reports `MISSING`
  rather than crashing), and the critic frames missing sections as "not yet
  written" rather than "you forgot".
- **Review-derived, not hand-authored, critic checklist (ICML only).**
  OpenReview lets you read the actual reviews for ICML 2026 — so why guess
  what reviewers care about? `mine_reviews.py` finds the recurring complaint
  patterns and attaches anonymized verbatim reviewer quotes; the critic
  speaks in reviewers' actual voice. Reviewer names are stripped at scrape
  time and never enter any reference file. CVPR and ACL have no public
  review corpus, so those critics fall back to a hand-authored domain-neutral
  `critique_checklist.md`; the ACL one is NLP-tuned (LLM-era baselines,
  prompt-template disclosure, annotation protocols, analysis/ablation-heading
  tolerance — ACL papers often fold design-choice isolation into an
  "Analysis" section, which `inspect.py` checks separately from "Ablation").
- **No predicted rating.** The ICML critic stays qualitative — it does not
  attempt to predict a reviewer score. The signal is "here are the gaps
  reviewers at this venue typically flag", not "you'd get a 4".
- **Citation-venue signature, used heuristically.** The extractor classifies
  each bib entry into a venue family (CV / ML / NLP / preprint / journal /
  other) and the aggregator reports both the corpus-aggregate share and the
  per-paper anchor-venue median (23% CV at CVPR, 26% ML at ICML, 8% NLP at
  ACL). The `paper-style` skill flags a draft whose anchor-venue share is in
  single digits as *possible* "style drift toward the wrong community" — but
  explicitly as a heuristic: modern ACL papers legitimately cite <10%
  NLP-family venues (arXiv + ML conferences dominate), so a low NLP share is
  a question, not a defect.
- **Balanced-brace bibtex scanner (ACL).** A couple of ACL tarballs bundle
  the entire 30–46 MB ACL Anthology `*.bib`. The CVPR/ICML extractor's
  lazy-`.*?\n}` regex catastrophically backtracks on those; the ACL
  `extract.py` replaces it with a single-pass brace-walking entry iterator
  (O(n), 46 MB in ~2 s) and skips `*.bib` files >5 MB so they don't pollute
  per-paper venue distributions — the bundled anthology is not that paper's
  own reference list. The same scanner is the recommended starting point for
  any future venue pipeline.
- **Lazy / stdlib-first.** Per the `ponytail` skill philosophy, the runtime
  scripts use only the Python standard library — no `pip install` needed to
  *use* the skills. Third-party deps (`openreview-py`, `python-dotenv`) are
  confined to the offline corpus-build scrapers for ICML.

## License

See [LICENSE](LICENSE).