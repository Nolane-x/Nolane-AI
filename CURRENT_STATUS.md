# Nolane-AI Current Research Status

This file is the short operational status index for active research. The README describes older accepted milestones and is not the authoritative indicator of the newest experimental branch state.

## Authority order

When claims disagree, use this order:

1. exact accepted release/evidence artifacts on the accepted ancestor;
2. frozen hosted verification records tied to an exact commit;
3. current production source and tests;
4. active pull-request specs/descriptions;
5. README or narrative summaries.

A draft PR, passing unit test, benchmark score, or successful external gate is not by itself an accepted capability release.

## R2.67

R2.67 is historical evidence, not current authority for the strong three-probe causal-necessity claim. Independent hosted validation found receipt-unit inconsistency and a lower-order ablation/exposure defect after the R2.67 freeze.

## R2.67.1 — accepted correctness parent

PR #61 (`R2.67.1 — genuine lower-order causal necessity hotfix`) was merged into `main` at commit `b789dd7a48f10f3afb1cf42ee62d3dc77dee200e` on 2026-08-19. It is the accepted parent boundary for canonical R2.68 research and supersedes historical R2.67 for corrected strong necessity semantics.

## R2.68 — canonical research milestone

PR #73 (`R2.68 — proof-carrying adaptive causal basis`) owns the canonical R2.68 namespace and targets accepted `main`.

Current bounded objective: replace the fixed exactly-three-probe assumption with a variable-cardinality causal-basis search while separating proposal search, validation, local necessity proof, global minimality proof and terminal authority.

Current Phase-A authority boundaries:

- +0 trainable parameters;
- target-preserving nuisance interventions are rejected before basis search rather than accepted as one-probe answer-copy channels;
- positive authored capability evidence is limited to certified 2-, 3-, and 4-probe families;
- every distinct legal intervention spec remains a distinct authority action even when finite discovery/validation behavior happens to coincide;
- validation intervention outputs may bind authority identity but cannot control proposal ordering; validation targets never train proposal search;
- full-basis public collision is basis-impossibility screening, not a `NecessityCertificate`;
- `NecessityCertificate` authority is restricted to non-empty proper subsets of the selected basis under subset-specific exposure;
- global lower-basis exclusion carries replayable `BasisCollisionCertificate` witnesses instead of trusting counters alone;
- `lower_basis_universe_digest` binds lower-basis identity, exposure, status and witness digest;
- lower-order search failure without an information-theoretic certificate is inconclusive;
- terminal evidence is disjoint and fail-closed;
- receipt counters represent actually attempted oracle observations, not planned/pre-rejected work;
- passing external I/O-only transfer does not override a failed core authority gate.

R2.68 remains a research draft. It is not an AGI claim, not a frontier-model-equivalence claim, and not an accepted readiness increase.

## Independent validation

Canonical regressions now incorporate defects found by independent workers around composition holdout leakage (#75), proper-subset necessity authority (#74/#77), nuisance intervention answer-copy shortcuts, failure-path observation accounting, and authority-universe collapse.

A validation-only child PR may be used to run the exact current #73 snapshot without merging validation-only files into the milestone.

## R2.68-T — complementary transfer research

PR #70 (`R2.68-T research — cross-task causal prior transfer`) is a separate complementary research track. It yields the canonical R2.68 milestone namespace to PR #73 and must not be cited as the R2.68 release.

## Promotion requirements

R2.68 has an exact accepted R2.67.1 ancestor. Remaining acceptance work includes production/source refreeze; reproducible authored evidence; pinned I/O-only external transfer on the frozen source; Python 3.11/3.13 hosted verification; protected lineage; independent proof/accounting challengers; Nolane World adjudication without forced convergence; exact source/test/evidence hashes; release artifacts; and post-merge exact-main verification.

Until those remaining conditions hold, status is **RESEARCH_DRAFT / NOT_ACCEPTED**.
