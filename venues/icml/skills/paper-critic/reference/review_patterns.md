# ICML 2026 — Reviewer Complaint Patterns (review-derived critic checklist)

Aggregated by `mine_reviews.py` from **2068 reviews** of **536 ICML spotlight papers**. (Skipped 8 reviews whose `strengths_and_weaknesses` had no parseable weakness text.) Reviewer identities were stripped at scrape time; snippets below are anonymized verbatim.

## How to use this checklist
For each pattern below, the critic asks whether the **draft** exhibits the issue. Patterns are sorted from most to least common in the ICML review corpus — the top ones are what an ICML reviewer is most likely to raise. The `review_count` is the number of reviews (out of 2068; spotlight papers tend to receive 3-4 reviews each) where the weakness was detected — not all reviews touch every issue, so a count of e.g. 80 is already a very common complaint.

Each pattern carries 1-3 anonymized verbatim snippets (drawn from the corresponding review sentences) so you can hear the actual reviewer voice. Apply each question to the draft's matching section; quote the draft where you can; do not paraphrase the issue inaccurately.

## Reviewer complaint patterns (frequency-ranked)

### 1. Writing / clarity issues  (n=493 reviews, 24% of review corpus)

**Critic question:** Would a grad student in an **adjacent** sub-area (not the author's own) follow the method section in one pass? Watch for undefined notation, jumps in the argument, and paragraphs that telegraph 'this will be clear to experts'.

**Reviewer examples (verbatim):**
- "It is unclear whether RV-aware filtering would still provide improvements."
- "- What is "thinking" of LRMs? Nothinking mode actually generates reasoning chains, although the length may be relatively short. It is unclear whether reasoning only counts as..."

### 2. Limited / insufficient experiments or scale  (n=488 reviews, 24% of review corpus)

**Critic question:** Does the experimental scope match the **scale of the claim**? A claim like 'our method works on diverse tasks' is unsupported by 1-2 tasks. Identify which tasks/datasets a reviewer would demand before accepting.

**Reviewer examples (verbatim):**
- "I also find the evaluation somewhat limited, which is maybe contributing to this for me – I'd be more confident in the results if the authors could show that PSR is useful beyond..."
- "- The evaluation scope is fairly limited and it's not clear if this method would work to mimic more complex, multi-faceted attributes/styles/instructions that could be steered..."

### 3. Technical / correctness errors  (n=106 reviews, 5% of review corpus)

**Critic question:** Spot-check claims against the math/code. Are equations internally consistent? Are theorem statements correct? A single incorrect lemma can sink an otherwise-good paper; reviewers will look.

**Reviewer examples (verbatim):**
- "As a result, comparing the derived steering vectors to baseline prompting feels somewhat unfair, as the prompting baseline is left to incur losses of incorrect completions, but if..."
- "Indeed, as far as I understand, while E3T requires a fixed-but-sensitive $\epsilon$ parameterisation, I expect its time and space complexities to be far lower than those UPD, and..."

### 4. Weak / missing / outdated baselines  (n=58 reviews, 3% of review corpus)

**Critic question:** Does the draft compare against the **most recent** and **strongest** baselines in its sub-field — not strawman or older methods that are easy to beat? Are there baselines from the last 12 months in the cited set?

**Reviewer examples (verbatim):**
- "- Missing baselines: The paper does not report and compare their approach to other methods doing adaptive steering moduling the steering coefficient, such as [1] and [2]."
- "But the clustering initialization baseline is primarily “random initialization”; for k-means, a more standard baseline is k-means++ (Arthur & Vassilvitskii), and for mixture order..."

### 5. Compute / efficiency concerns  (n=58 reviews, 3% of review corpus)

**Critic question:** Does the draft report compute/memory/inference cost honestly? If the method trades quality for cost, is the trade-off numbers-on-the-table rather than vague? A reviewer will check if 'efficient' is benchmarked.

**Reviewer examples (verbatim):**
- "- Latent-Space Critic: By moving the critic to the continuous latent space, the method amortizes the computational cost of the CO solver, bypassing the need to differentiate..."
- "Computational Cost Acknowledged but Not Quantified: The paper notes that training soft tokens requires full backpropagation, making it computationally comparable to fine-tuning..."

### 6. Missing / incomplete ablation study  (n=52 reviews, 3% of review corpus)

**Critic question:** If the draft makes contribution claims, is each one isolated by an ablation that **removes** that specific component while keeping the rest fixed? A paper with N contribution claims needs N ablations (one per claim).

**Reviewer examples (verbatim):**
- "ry between the stiff and flat subspaces, the lack of ablation makes the robustness of this heuristic questionable."
- "However, without an ablation study, it is unclear how quickly this static projection matrix degrades and becomes misaligned with the model's true trajectory."

### 7. Limited / incremental novelty  (n=41 reviews, 2% of review corpus)

**Critic question:** Is the novelty claim something a reviewer can locate in the method — i.e. not 'we apply X to Y'? Incremental combinations are accepted when the combination itself is non-obvious; spell out why it is.

**Reviewer examples (verbatim):**
- "The benchmark construction methodology is not particularly novel."
- "Limited novelty compared to prior cipher-based jailbreak attacks."

### 8. Limited / narrow datasets or benchmarks  (n=40 reviews, 2% of review corpus)

**Critic question:** Does the draft evaluate on the standard benchmarks for its sub-field, or introduce a new one? If new, is there a justification for why the standard ones are insufficient (cherry-picking suspicion otherwise)?

**Reviewer examples (verbatim):**
- "The authors rely their empirical experiments on single dataset for prompts, with many theoretical assumptions around $\epsilon$ nature those assumptions likely break down in..."
- "Qwen-family) or more advanced reasoning benchmarks (e."

### 9. Restrictive / unrealistic assumptions  (n=29 reviews, 1% of review corpus)

**Critic question:** Are the assumptions stated up front and defended? Strong / unrealistic assumptions are fine when acknowledged and their impact assessed; unstated assumptions invite reviewer skepticism.

**Reviewer examples (verbatim):**
- "The theoretical results rely on several fairly strong assumptions, such as approximate orthonormality, faithful SAE reconstruction, semantic orthogonality, and feature..."
- "This assumes that a non-thinking model does not try to do any internal reasoning, which to me seems like a strong assumption that should at least be discussed."

### 10. Reproducibility / code missing  (n=17 reviews, 1% of review corpus)

**Critic question:** Are the experimental details (hyperparameters, seeds, hardware, dataset versions) sufficient for replication? Is a code URL promised? Camera-ready reproducibility is now scored at ICML; its complete absence costs the paper at review time.

**Reviewer examples (verbatim):**
- "- No code for replication is given"
- "Reproducibility is important."

### 11. Overclaiming / unsupported claims  (n=15 reviews, 1% of review corpus)

**Critic question:** For each superlative ('outperforms', 'state-of-the-art', 'first to'), can you point to a specific table/figure that backs it with numbers? If the claim is hedged ('competitive') is that a reframe of an SOTA claim that the experiments don't support?

**Reviewer examples (verbatim):**
- "- Exaggerated claims. The paper provides evaluation on only 2 LLM with relatively small size. While this is not a problem in itself, it is however strange to find in the abstract..."
- "I think this claim is exaggerated since the authors introduce a different hyperparameter."

### 12. Missing / incomplete related work or citations  (n=15 reviews, 1% of review corpus)

**Critic question:** Does the draft cite and differentiate the closest prior art? Are there missing references — large adjacent works a reviewer will know? Missing 1-2 obvious citations is a small flag; missing a body of work is a major flag.

**Reviewer examples (verbatim):**
- "Lack of Related Work: One alone section to show the difference and improvement compared with the previous is necessary, which can better help me understand the value of the work."
- ", Language-Table are missing references."

### 13. Missing theoretical / formal analysis  (n=13 reviews, 1% of review corpus)

**Critic question:** If the draft makes a formal claim (convergence, sample complexity, optimality), is there a theorem/proof or pointer to one? If only an empirical claim, is the analysis still missing that a reviewer will want (e.g. why the method works)?

**Reviewer examples (verbatim):**
- "Status of Core Claims: Claim 3.1 serves as the paper’s foundation but is presented without a full formal proof. While the complexity of such a proof is acknowledged, it remains a..."
- "Equation (14) merely assumes that the quantization error can be fitted by a fixed channel-wise linear scaling computed offline, yet it provides no theoretical justification for..."

### 14. Generalization / OOD / robustness concerns  (n=5 reviews, 0% of review corpus)

**Critic question:** If the draft claims generalization (across datasets/domains/scales), is there direct evidence of it? OOD or domain-shift claims without OOD experiments are flagged immediately.

**Reviewer examples (verbatim):**
- "Lack of robustness evaluation for the pruning triggers."
- "Different training runs could potentially produce different factor decompositions, raising concerns about the robustness of the interpretability claim."

### 15. Unclear / weak motivation  (n=2 reviews, 0% of review corpus)

**Critic question:** Can a one-line answer to 'why is this paper needed?' be reconstructed from the intro? If the gap is implicit ('existing methods don't do X') does the draft cite the prior work that does X and what failed at the X attempt?

**Reviewer examples (verbatim):**
- "- The paper clearly states its contributions at the end of Section 1. I think this is in general good. However, I am really missing a motivation or justification why these..."
- "On the other hand, I think that the main weakness of the paper is the lack of clear motivation for restricting each of the different types of causal discrimination by itself, and..."

## Field-by-field meaning (for the runtime script)
`mine_reviews.py` reports these metrics; `inspect.py` may surface some during a draft scan when the matching pattern is detected in the draft text (lightweight match on cleaned section text):

- `baselines` — Weak / missing / outdated baselines (review_corpus_count=58)
- `ablation` — Missing / incomplete ablation study (review_corpus_count=52)
- `novelty` — Limited / incremental novelty (review_corpus_count=41)
- `clarity` — Writing / clarity issues (review_corpus_count=493)
- `experiments_scale` — Limited / insufficient experiments or scale (review_corpus_count=488)
- `theory_analysis` — Missing theoretical / formal analysis (review_corpus_count=13)
- `overclaim` — Overclaiming / unsupported claims (review_corpus_count=15)
- `motivation` — Unclear / weak motivation (review_corpus_count=2)
- `reproducibility` — Reproducibility / code missing (review_corpus_count=17)
- `dataset_benchmark` — Limited / narrow datasets or benchmarks (review_corpus_count=40)
- `related_work` — Missing / incomplete related work or citations (review_corpus_count=15)
- `soundness_error` — Technical / correctness errors (review_corpus_count=106)
- `generalization` — Generalization / OOD / robustness concerns (review_corpus_count=5)
- `efficiency_cost` — Compute / efficiency concerns (review_corpus_count=58)
- `assumptions` — Restrictive / unrealistic assumptions (review_corpus_count=29)

_Generated by mine_reviews.py from data/reviews/*.json. Reviews were anonymized at scrape; only content fields and verbatim snippets appear here._