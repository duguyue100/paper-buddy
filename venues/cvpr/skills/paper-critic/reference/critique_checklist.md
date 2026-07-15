# CVPR Critic Checklist — Domain-Neutral Advisor Questions

Use these questions on any draft section, regardless of sub-field. Each maps to a concrete thing a CVPR reviewer probes. Where a number is cited, it is the corpus median from 106 accepted orals (see `cvpr_expectations.md`). A deviation is a question, not a verdict — ask the author to justify, do not assume it is wrong.

## Abstract
- Does the abstract state the **problem**, the **insight/key idea**, and the **quantitative result**? CVPR abstracts run a median of 8 sentences / 169 words — shorter is usually missing the result, longer is usually spilling method detail that belongs in the body.
- Is there a **single concrete number** (gain, speed-up, dataset size) the reader can anchor on? Vague abstracts ("we achieve competitive results") are the #1 reason an abstract reads as weak.
- Are contributions enumerated here? If yes, **move them to the intro** — only ~2% of orals list contributions in the abstract; the abstract should be a pitch, not a table of contents.

## Introduction
- Does the first paragraph open with a **hook** (a claim, statistic, or question) that motivates a reader outside your sub-field? ~97% of orals open with a claim; an anecdotal hook is a red flag for CVPR.
- Is there a **gap statement** — what specifically did prior work *not* do that this paper does? If the gap is implicit, make it explicit.
- If contributions are enumerated, are they **falsifiable claims** ("we show X achieves Y on Z"), not feature lists ("we use a novel attention mechanism")? ~43% of orals enumerate; the strong ones make claims you can check against the experiments.
- Does the last paragraph **forecast the structure** or restate the headline result? A weak closing paragraph is a common reviewer complaint.

## Related Work
- Is related work organized **thematically** (by problem family) rather than **chronologically**? A flat list of citations reads as "I skimmed the area".
- Are the closest competitors **named and differentiated** in one sentence each? "X does A; we do B" is the CVPR norm — ~96% of orals have a Related Work section (median ~390 words); if yours is far shorter, you may be under-situating.
- Does it cite the **venue's recent prior art** (CVPR/ICCV/ECCV)? If your CV-family cite share is well below the corpus median (~23%), a reviewer will check — the `paper-style` skill measures this.

## Method
- Is the method **named** up front (an acronym with its expansion)? Most orals name their contribution; an unnamed method is harder for reviewers to refer to.
- Is there at least one **formal definition** (equation, loss, or algorithm box)? Median ~11 equation environments, domain-sensitive (theoretical papers more, applied papers fewer) — if zero, reviewers ask "what is the method formally?".
- Is there a **notation table** or consistent notation? Inconsistent symbols across sections is a silent rejection trigger.
- For each design choice, is there a one-sentence **rationale** ("we use X because Y")? Choices without rationale read as arbitrary; the ablation should later confirm each one.

## Experiments
- Are there **baselines** that are recent and strong (not strawmen)? A reviewer's first check. No specific count is a rule, but tables are the unit — median ~4 tables.
- Is there an **ablation** that isolates each claimed contribution? ~66% have an explicit "Ablation" heading; even those without usually ablate inline. If your paper claims 3 contributions, the ablation should remove each one. A missing ablation is the single most common CVPR rejection reason.
- Does every **SOTA/outperform** claim (median ~10 mentions per paper) map to a **specific table or figure** with numbers? A superlative with no \ref{tab...} is a red flag.
- Are **datasets and metrics standard** for the sub-field? If you introduce a new dataset/metric, you must justify why the standard ones are insufficient — otherwise reviewers suspect you cherry-picked.
- Are **failure cases** shown or limitations acknowledged? ~some orals have a "Limitations" section; not mandatory, but its absence with an ambitious claim invites reviewer skepticism.

## Conclusion
- Does it **recap the result** and state **limitations / future work**? A conclusion that only summarizes the method (not the result) is weak.
- Does it avoid **new claims** not supported by the experiments? A common silent flaw.

## Cross-cutting (any section)
- **Claim-to-evidence ratio**: for each superlative ("novel", "state-of-the-art", "first to"), is there a concrete result backing it? Run `inspect.py` — it flags superlatives with no nearby `\ref`.
- **Hedging density**: median superlative mentions (10) vs hedging words ("can/may/typically"); a draft with heavy hedging and few superlatives reads as under-confident; the reverse reads as over-claiming. Neither is wrong, but the imbalance is worth questioning.
- **Logical flow between sections**: does the last sentence of each section motivate the next? If a reviewer can't answer "why are you telling me this now?", the narrative is broken.
- **Reproducibility signals**: implementation details, code URL, dataset release. Not required for review, but their absence at camera-ready is noticed.

## How to use this checklist at runtime
1. Run `python scripts/inspect.py <draft.tex or dir> [section]` to extract the section text and structural signals (claims with no \ref, hedging density, missing standard subsections).
2. For each present section, apply the questions above. For each *missing* section the checklist expects, raise it as a finding ("no Ablation heading detected — what 3 design choices should be isolated?").
3. Quote the draft where possible; do not invent text. When a corpus number is relevant, cite it ("corpus median 4 tables; you have 1 — what experiments are planned?").
4. End with a **prioritized action list** (high/medium/low), each item a concrete question or a specific edit, not a vague "improve clarity".

_Checked items are domain-neutral. Numbers in parentheses come from `cvpr_expectations.md`. When a field is domain-sensitive, ask for a domain justification rather than enforcing the median._