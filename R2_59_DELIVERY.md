# Nolane-AI R2.59 Delivery — Active Diagnostic Repository Probe Synthesis

Status: **ACCEPTED_BOUNDED_CAPABILITY**

R2.59 transfers R2.58's active-experiment principle into repository repair. When sparse executable tests leave multiple existing R2.52 patch hypotheses alive, the runtime now predicts their behavior on legal unlabeled inputs, selects the probe with the strongest deterministic disagreement, queries the reference oracle only for that selected probe, and independently verifies a unique survivor before terminal acceptance. It adds **0 trainable parameters**.

## Mechanism

- content-addressed `RepositoryProbe` identities over canonical JSON-scalar arguments
- executable hypothesis filtering from sparse `PatchTest` evidence
- target-label-free candidate prediction over the legal probe domain
- deterministic minimax ambiguity ranking with collision-mass and partition-count tie-breaks
- candidate-ID/order-invariant probe selection
- hard selection-oracle budgets with no probe reuse
- fail-closed handling for empty version spaces, uninformative probes, budget exhaustion and oracle errors
- independent terminal verification separated from selection-label accounting
- explicit receipts for survivor counts, partition signatures, oracle calls, candidate evaluations and false terminal accepts

## Frozen authored repository evidence

Across six protected R2.52 heldout episodes:

- repository size: **5–6 Python files**
- call depth: **4–5**
- enumerated patch candidates: **75**
- initial sparse tests: **4 per episode**
- legal probe space: **2,401 inputs**
- passive initial-only exact: **0/6**
- target-independent random one-probe exact: **1/6**
- R2.59 active exact: **6/6**
- gain over matched random one-probe: **+5 episodes**
- selection oracle calls: **exactly 1 per episode**
- exact target macro set: **6/6**
- candidate-ID/order invariance: **PASS**
- target outputs used during probe generation: **0**
- false terminal accepts: **0**
- independent terminal verification: **2,401/2,401 cases per accepted episode**

## Pinned external NumPy transfer

External oracle: **NumPy 2.4.6 `numpy.gcd`**. The adapter receives callable I/O only and does not inspect NumPy implementation source.

Four host-authored executable behavioral hypotheses are deliberately chosen to agree on the same two initial oracle observations. Under a fixed 625-input domain:

- initial survivors: **4/4**
- passive initial-only exact: **FAIL**
- target-independent one-probe exact: **FAIL**, leaving 2 survivors
- R2.59 active selection queries: **1**
- selected probe: `(-10, -2)`
- selected partition count: **4**
- largest partition: **1**
- active exact: **PASS**
- false accepts: **0**
- independent verification: **625/625**
- total oracle calls including initial evidence, matched baseline, active selection and final verification: **629**
- trainable parameters: **0**

This transfer is causal evidence for active diagnostic selection against one independently sourced pure integer oracle. The candidate set itself is host-authored, so it is not evidence for independent repository hypothesis generation or general repository coding.

## Fresh hosted verification

Capability/gate commit: `5abcbbb3b5c159519566fdbdbe353f733871614d`

GitHub Actions push run: `32116854204`; main job `95648197603` — **success**.

- focused R2.59 tests: **7/7**
- exact pinned external JSON recomputation: **success**
- exact frozen Phase-A recomputation: **success**
- protected parent/repository tests: **186/186**
- Python 3.11 / 3.13: **success / success**
- external artifact: `9317002843`
- added trainable parameters: **0**

## Nolane World 0.8.0

Fresh W5 world `world4_e293c77f03754ec4` reached epoch 6. Audit digest `8ec83909d2b5bb48895124e8071135bf0edca9f0187ce908a58cda1d91e5d605` is valid. W5 remains **FAIL**, score **0**; non-convergence is deliberately preserved.

The audit highlights several blockers: R2.59 cannot recover a missing target hypothesis; probe domains remain host-provided and scalar; stateful/effectful experiments are absent; the external candidate ecology is host-authored; and exhaustive final verification dominates total oracle cost.

## Readiness

Internal Coding-AGI engineering-readiness: **48.1/100**, up **+0.3** from R2.58's canonical **47.8**. The movement is intentionally small because R2.59 demonstrates a real causal active-diagnostic transfer at repository-hypothesis level, but still consumes finite host-supplied candidate/probe spaces and does not establish broad issue resolution. This score is an internal engineering heuristic, not an AGI probability.
