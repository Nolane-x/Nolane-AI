# R2.68 Proof-Carrying Adaptive Causal Basis — Design

## Status

Design approved for implementation. This milestone is a bounded capability step toward more autonomous causal reasoning. It is not an AGI claim.

## Parent and coordination boundary

R2.68 must build on the corrected R2.67.1 causal-necessity semantics, not historical R2.67 semantics. The implementation branch is isolated from the active R2.67.1 production branch and must not mutate R2.67.1 artifacts. Before promotion, the R2.68 branch must be updated to an accepted R2.67.1 parent and rerun the full protected lineage.

## Goal

Replace the fixed exactly-three-probe causal-composition assumption with an adaptive, proof-carrying causal-basis search that can discover a sufficient intervention basis of variable cardinality while strictly separating heuristic search from proof authority.

## Core principle

Search may propose. Evidence may authorize. A bounded or heuristic search miss is never an impossibility certificate.

R2.68 distinguishes:

1. **Sufficiency** — a basis plus composition reproduces public selection/validation evidence and independent terminal evidence.
2. **Local irreducibility** — every proper subset required by the local certificate policy is independently shown insufficient under its own subset-specific exposure schema.
3. **Global minimality** — all legal bases of lower cardinality are either conclusively insufficient by proof or conclusively rejected by successful contradictory alternatives. If any lower-order possibility remains unproved because search is incomplete, the result is minimality-inconclusive.

A sufficient candidate may be returned without a global-minimality claim, but promotion as a certified minimal basis is forbidden unless global minimality is proven.

## Architecture

### Generic adaptive basis model

Create `cogcoder/r268_adaptive_causal_basis.py` with immutable public receipt types:

- `NecessityCertificate`
- `AdaptiveCausalBasisCandidate`
- `AdaptiveCausalBasisStructureReceipt`
- `AdaptiveCausalBasisReceipt`

`AdaptiveCausalBasisCandidate` stores a tuple of interventions and profiles of length `k`, where `1 <= k <= max_basis_size`. Cardinality-specific classes such as `ThreeProbe*`, `FourProbe*`, or `FiveProbe*` are forbidden in the R2.68 public model.

### Correct-parent reuse

R2.68 reuses trusted primitives from corrected R2.67.1 where semantics are already sound: positional schema canonicalization, intervention enumeration and validation, semantic profile identity, finite-value normalization, expression evaluation and DSL semantics, subset-specific shared/free-field recomputation, public target-collision detection, and observed-case accounting principles. R2.68 must not mutate frozen R2.67.1 production code.

### Variable-arity composition search

Implement a generic expression synthesizer over fields `__p0 ... __p{k-1}` plus subset-specific free context fields. Phase A supports `k=1..4` under explicit budgets and the existing trusted arithmetic/logic DSL.

The search must require every selected probe field to occur structurally in a candidate being considered as a `k`-basis, use deterministic semantic deduplication, expose per-basis and global candidate budgets, and schedule semantic bases independently of positional names or content-addressed IDs. Budget exhaustion is always inconclusive, never an impossibility certificate.

### Proof-carrying necessity layer

`NecessityCertificate` binds proof authority to the exact lower-order claim. Required identity fields are basis semantic profile IDs, tested subset profile IDs, subset cardinality, subset-specific exposed field names, canonical public evidence digest, proof kind, and proof witness digest.

Phase-A proof kind is `public_target_collision`: two public examples are identical in the complete exposed lower-order evidence vector but have distinct normalized targets. This proves that no deterministic expression of that exposed evidence can satisfy both examples.

Certificate verification recomputes the witness from public evidence. Serialized claims are not trusted by declaration. A collision certificate cannot be transferred from one subset to another unless the target subset independently recomputes the same exposure and witness. Each subset must recompute its own free fields.

### Adaptive cardinality search

Search basis sizes in increasing cardinality. For each `k`, enumerate legal semantic intervention bases using deterministic fair scheduling, synthesize a composition from selected probes plus basis-specific free fields, validate on disjoint validation evidence, independently validate learned probe expressions, build necessity certificates for lower-order subsets when public information-theoretic witnesses exist, mark unresolved lower-order claims inconclusive when proof is absent, and terminally re-observe the exact selected interventions before final acceptance.

The first sufficient basis is not automatically globally minimal. Global minimality depends on the complete lower-cardinality proof ledger.

### Fail-closed authority states

The public receipt must distinguish at least:

- `adaptive_basis_discovered`
- `sufficient_but_minimality_inconclusive`
- `lower_order_basis_found`
- `necessity_certificate_missing`
- `basis_search_budget_exhausted`
- `probe_synthesis_failed`
- `probe_validation_failed`
- `terminal_probe_oracle_error`
- `terminal_probe_validation_failed`
- `final_terminal_oracle_error`
- `final_validation_failed`
- `no_adaptive_basis`

Any oracle error, non-finite observation, malformed evidence, invalid certificate, or authority-ledger inconsistency fails closed with zero false terminal accepts.

### Exact evidence accounting

Every receipt reports actual attempted observations, never planned denominators. Counters include intervention discovery oracle calls, basis selection observations, probe validation attempted/exact, necessity-certificate witness observations, terminal selected-probe attempted/exact, final terminal attempted/exact, and total oracle calls. Hosted benchmark wrappers that call the oracle outside the engine expose a separate end-to-end exact ledger.

## Phase-A benchmark

Create `benchmarks/kfigg/r268_adaptive_causal_basis.py` with a frozen authored mixed-cardinality suite. It must contain structurally distinct tasks whose certified minimal basis sizes are 1, 2, 3, and 4.

Required adversarial properties:

- intervention identity renaming invariance;
- field permutation invariance;
- basis scheduling/order invariance under a tight global search budget;
- a lower-order no-collision search-miss case that must remain inconclusive;
- outside-authorized-grammar or misspecified-oracle control that fails closed;
- exact receipt accounting;
- zero false terminal accepts;
- `trainable_parameter_count == 0`.

The suite must not equate milestone number R2.68 with basis size 4. Mixed cardinalities are mandatory.

## External transfer

External evidence is a separate hosted gate and must use callable I/O only. The external target is frozen before measurement and must be structurally distinct from the authored family. Do not promote an external result if it is merely an isomorphic renaming of an authored formula.

An external transfer is not required to write the core Phase-A implementation, but it is required before an accepted R2.68 capability release or readiness increase.

## TDD and protected regressions

TDD is mandatory and RED must be observed before production implementation. Minimum contracts cover adaptive cardinality 1/2/3/4, absence of fixed-three assumptions, certificate binding to exact subset exposure, no certificate reuse across different free-field schemas, heuristic-search miss without collision remaining inconclusive, a real lower-order sufficient basis blocking higher-order minimality promotion, rename/permutation invariance, fair global budget scheduling, partial/failure-path observed-case accounting, terminal selected-probe re-observation, oracle failure fail-closed behavior, deterministic replay, and accepted R2.67.1/R2.66 protected regressions.

## Promotion boundary

R2.68 may be called `ACCEPTED_BOUNDED_CAPABILITY` only after corrected R2.67.1 is an accepted ancestor, source/protocol is frozen before final evidence measurement, exact authored evidence recomputes byte-for-byte, a pinned I/O-only external transfer passes, cross-Python hosted tests pass, protected lineage passes, an independent challenger lineage attacks proof authority and accounting, Nolane World adjudication is recorded without forcing convergence, and no automatic AGI-readiness increase is granted merely for bug fixes or receipts.

## Non-claims

R2.68 does not establish open-ended causal language invention, unbounded intervention cardinality, stateful/temporal experimentation, filesystem/network scientific autonomy, human-level reasoning, or AGI. It establishes a bounded architecture for adaptively discovering and proof-scoping a causal intervention basis without treating search failure as proof.