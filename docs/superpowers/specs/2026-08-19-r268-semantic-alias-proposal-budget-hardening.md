# R2.68 Semantic-Alias Proposal Budget Hardening

## Status

Release-authority hardening for canonical R2.68. This document narrows scheduler semantics; it does not widen the capability claim or add trainable parameters.

## Defect

R2.68 correctly keeps concrete intervention identities distinct for proof authority. That creates a resource-invariance hazard when two distinct legal interventions produce identical discovery behavior: a scheduler that allocates or repeatedly spends candidate budget per authority identity can make the solved/inconclusive outcome depend on how many behavior-identical aliases exist.

Independent validation exposed both levels of this defect. The semantic-alias fairness line (#80/#81/#83) required alias count not to dilute a tight finite budget. Stronger challenger #84 then forced proposal misses and measured repeated work directly: hosted run `32237610280` observed four proposal-search calls for the aliased task versus one for the control while accepted R2.67.1/R2.66 safety remained green.

## Required separation

R2.68 therefore separates three identities:

1. **Authority identity** — concrete intervention-bound and never collapsed merely because finite observations coincide.
2. **Proposal-equivalence identity** — discovery-only scheduling/cache identity. It may share one proposal-search receipt only when the basis has the same intervention positions and the same normalized discovery probe-output vectors under the canonical proposal key.
3. **Validation/proof identity** — concrete authority basis. Validation outputs, subset certificates, lower-basis certificates and terminal evidence are recomputed or checked for the concrete basis and are never inherited as authority from a proposal alias.

Validation evidence must not enter the proposal-equivalence key, proposal ordering, search generation or budget allocation.

## Budget semantics

For each cardinality, the complete authority universe is still enumerated. Collision-certified lower bases remain represented independently in the proof ledger. For non-collision bases:

- candidate budget is allocated over unique discovery proposal-equivalence classes;
- the synthesizer is called at most once per proposal class;
- the resulting search receipt is cached and reused for later concrete authority aliases in that class;
- cached reuse consumes zero additional composition candidates and is permitted even when the global search budget has been exhausted by the original class search;
- every concrete basis remains separately counted as considered and separately passes selection replay, disjoint validation, local necessity proof, global proof-ledger accounting and terminal authority before acceptance.

A cached proposal failure may be reused as a search result, but it is never converted into an impossibility certificate. Search miss remains inconclusive unless an independent information-theoretic certificate exists.

## Frozen contracts

Release regression must preserve all of the following simultaneously:

- authority-distinct aliases remain present in `legal_interventions`, `semantic_profiles` and the lower-basis proof universe;
- adding discovery-equivalent aliases does not change a matched tight-budget solved/global-minimal outcome;
- adding discovery-equivalent aliases does not increase proposal synthesizer call count or `composition_candidates_considered` for the same proposal-class universe;
- validation cannot control proposal keys or scheduling;
- proof certificates remain bound to concrete authority identities and exact exposed evidence;
- +0 trainable parameters and zero false terminal accepts.

## Promotion consequence

Any R2.68 freeze or evidence created before this hardening is historical pre-fix evidence only. Accepted R2.68 requires a fresh exact-head source/evidence lock and hosted replay after the canonical cache/reuse regression is green on Python 3.11 and 3.13, followed by the normal canonical, protected-lineage, external, Nolane World, release-ZIP and post-merge gates.
