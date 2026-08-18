# Nolane-AI R2.60 Delivery — Active Diagnostic Repository Probe Synthesis

Status: **ACCEPTED_BOUNDED_CAPABILITY**

R2.60 adds a zero-parameter active diagnostic layer to repository repair. When sparse executable tests leave multiple existing R2.52 patch hypotheses alive, the runtime predicts their behavior on legal unlabeled inputs, selects the most discriminating probe under a hard oracle budget, consumes a label only for that selected probe, and independently verifies a unique survivor before terminal acceptance.

R2.60 is additive to the accepted R2.59 Budgeted Semantic Intervention Index. It was rebased onto the complete R2.59 release and the final gate reruns R2.59 through R2.41 on the same tree.

## Mechanism

- content-addressed `RepositoryProbe` identities over canonical JSON-scalar positional arguments
- executable filtering of repository patch hypotheses from sparse `PatchTest` evidence
- target-label-free prediction of each surviving candidate over a legal probe domain
- deterministic minimax ambiguity ranking with collision-mass and partition-count tie-breaks
- candidate-ID/order-invariant probe selection
- hard selection-oracle budgets and no probe reuse
- fail-closed behavior for empty version spaces, uninformative probes, budget exhaustion, oracle errors and target outcomes outside the candidate version space
- independent terminal verification separated from selection-label accounting
- explicit receipts for survivors, partitions, oracle calls, candidate evaluations, verification failures and false terminal accepts
- **0 trainable parameters**

## Frozen authored repository evidence

Across six protected R2.52 heldout episodes:

- repository size: **5–6 Python files**
- call depth: **4–5**
- enumerated patch candidates: **75**
- initial sparse tests: **4 per episode**
- legal probe space: **2,401 inputs**
- passive initial-only exact: **0/6**
- target-independent one-probe exact: **1/6**
- R2.60 active exact: **6/6**
- gain over matched one-probe baseline: **+5 episodes**
- active selection oracle calls: **exactly 1 per episode**
- exact target macro set: **6/6**
- candidate-ID/order invariance: **PASS**
- probe generation reading target outputs: **NO**
- false terminal accepts: **0**
- independent terminal verification: **2,401/2,401 cases per accepted episode**

The terminal verification cost is deliberately reported separately. R2.60 demonstrates selection-label efficiency; it does **not** demonstrate lower total oracle cost because final verification remains exhaustive.

## Pinned external NumPy transfer

External oracle: **NumPy 2.4.6 `numpy.gcd`**. The adapter receives callable I/O only; NumPy implementation source is not parsed into the mechanism.

Four host-authored executable behavioral hypotheses are constructed to agree on the same two initial observations. Under a fixed 625-input domain:

- initial survivors: **4/4**
- passive initial-only exact: **FAIL**
- target-independent one-probe exact: **FAIL**, leaving 2 survivors
- R2.60 active selection labels: **1**
- selected probe: `(-10, -2)`
- selected partition count: **4**
- largest partition: **1**
- active exact: **PASS**
- false terminal accepts: **0**
- independent verification: **625/625**
- total oracle calls including initial evidence, matched baseline, active selection and final verification: **629**
- trainable parameters: **0**

This is causal external evidence for the diagnostic-selection mechanism against one independently sourced pure integer oracle. The four candidate hypotheses themselves are host-authored, so this is not independent candidate-generation evidence or general repository coding evidence.

## Final source-locked hosted verification

Capability/source-lock head: `eef1bf246a20cf682040dc48a4481380906d15ec`

Accepted parent release: `1e59bd13baabba0e1ba71294aa02365d4e661ee0` (R2.59).

GitHub Actions push run: `32119199311`; focused/external/lineage job `95655513375` — **success**.

A second PR-merge run `32119203757` / job `95655528685` also completed successfully against the synthetic PR merge tree.

Final push gate results:

- locked source blobs: **exact match**
- accepted R2.59 release manifest: **verified**
- focused R2.60 tests: **7/7**
- exact frozen R2.60 Phase-A recomputation: **success**
- exact frozen NumPy transfer recomputation: **success**
- direct protected R2.52 repository tests: **6/6**
- accepted R2.59 tests: **12/12**
- protected R2.58 tests: **11/11**
- protected R2.57→R2.50 tests: **100/100**
- protected R2.49→R2.41 tests: **69/69**
- total protected parent relevant tests: **198/198**
- Python 3.11 / 3.13 R2.60 focused tests: **success / success**
- external artifact: `9317856476`
- added trainable parameters: **0**

## Nolane World 0.8.0

Fresh W5 world `world4_88cbc495caa644cb` reached epoch 7 with 60 active seconds credited and 15 audit events. Audit digest `4825bb01fff57b28f37d79e43a5d6a16ca877dd6cbd12d5239405ad11606b6fb` is valid. W5 remains **FAIL**, score **0**; non-convergence is deliberately preserved.

The unresolved blockers remain substantive: target behavior can be absent from the supplied candidate version space; legal probe domains are finite and host-provided; the representation excludes stateful/temporal/filesystem/network/effectful experiments; the external hypothesis ecology is host-authored; external breadth is one integer ufunc; exhaustive final verification dominates total oracle cost; and independent challengers/counterfactual representations remain insufficient for W5 convergence.

## Readiness

Internal Coding-AGI engineering-readiness: **48.1/100**, up **+0.3** from R2.59's **47.8**. The movement is intentionally small: R2.60 adds a causally validated repository-level evidence-acquisition mechanism and a fresh external oracle family relative to R2.59's reused `linearstep` distribution, but it still consumes finite host-supplied candidate/probe spaces and does not establish broad autonomous issue resolution. This is an internal engineering heuristic, not an AGI probability.
