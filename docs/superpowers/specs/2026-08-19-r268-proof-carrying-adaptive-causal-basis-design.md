# R2.68 Proof-Carrying Adaptive Causal Basis — Design

## Status

Research draft under hosted verification. R2.68 is a bounded capability step toward more autonomous causal reasoning. It is not an AGI claim, frontier-equivalence claim, or accepted readiness increase.

## Accepted parent boundary

R2.67.1 is accepted on `main` at commit `b789dd7a48f10f3afb1cf42ee62d3dc77dee200e`. Canonical R2.68 PR #73 targets that accepted parent. Historical R2.67 is not authority for the corrected strong causal-necessity semantics.

All final R2.68 evidence, locks, manifests and release claims must be regenerated after production stabilizes on this exact accepted-parent lineage. R2.68 does not mutate frozen R2.67.1 artifacts.

## Goal

Replace the fixed exactly-three-probe causal-composition assumption with an adaptive, variable-cardinality causal-basis search that strictly separates heuristic proposal search, validation authority, local proper-subset necessity, global lower-basis impossibility proof, and terminal acceptance.

## Core principle

**Search may propose. Evidence may authorize.** A bounded search miss is never an impossibility certificate.

R2.68 distinguishes four claims:

1. **Sufficiency** — a selected basis and composition fit discovery evidence, pass disjoint validation evidence, synthesize executable probe expressions, and pass independent terminal re-observation.
2. **Local irreducibility** — every non-empty proper subset of the selected basis has an independently recomputed subset-specific public collision certificate.
3. **Global lower-basis exclusion** — every legal basis of smaller cardinality carries a replayable public basis-collision certificate or global minimality remains inconclusive.
4. **Global minimality** — both the complete lower-cardinality ledger and the complete selected-basis proper-subset ledger are proof-complete.

A sufficient candidate may be returned while minimality is inconclusive. Promotion as a certified minimal basis is forbidden unless both proof layers are complete.

## One-probe and nuisance boundary

Basis size 1 remains representable architecturally, but Phase A does not promote a positive one-probe minimality claim because there is no complete zero-basis proof mechanism.

A target-preserving intervention is not authority-eligible when its discovery intervention outputs equal the un-intervened discovery target on every discovery row. Such a profile can create an answer-copy channel where `__p0` merely reproduces the target. It is rejected before basis search.

This rule is an anti-smuggling guard, not proof of causality. It consults discovery evidence only and grants no positive capability authority by itself.

## Evidence partitions

- **Discovery evidence** may influence candidate construction, proposal scheduling, expression synthesis and anti-smuggling admission.
- **Validation intervention outputs** may distinguish authority identities and verify already-proposed structures, but may not alter proposal ordering or composition training examples.
- **Validation targets** are authority-only and may not be used for proposal generation/ranking.
- **Terminal evidence** is disjoint from all learning/validation query inputs and is used only after a candidate has been selected and executable probe expressions have been validated.

Composition candidate synthesis receives discovery rows only. Independent challenger PR #75 established a historical RED boundary for validation leakage; canonical R2.68 keeps that contract as a permanent regression.

## Intervention authority universe

Every legal intervention spec that survives context validation, finite-value checks, non-degeneracy and target-effect admission remains a distinct authority action.

Finite evidence equivalence is not permission to erase a legal intervention from the global-minimality universe. `InterventionProfile.semantic_profile_id` therefore binds both observed behavior and the content-addressed intervention identity. Two different intervention specs remain distinct even if their discovery and validation outputs happen to coincide on the finite corpus.

Proposal ordering is a separate concept. `_profile_proposal_key` uses discovery behavior plus intervention identity and does not use validation outputs or validation targets. This prevents validation evidence from steering bounded search order while preserving an intervention-distinct proof universe.

## Generic adaptive basis model

Public R2.68 authority types include:

- `NecessityCertificate`
- `BasisCollisionCertificate`
- `AdaptiveCausalBasisCandidate`
- `AdaptiveCausalBasisStructureReceipt`
- `AdaptiveCausalBasisReceipt`

The architecture supports `k=1..4` under explicit budgets and the trusted arithmetic/logic DSL. Current positive Phase-A capability evidence is restricted to certified 2-, 3-, and 4-probe families.

Cardinality-specific public classes such as `ThreeProbe*`, `FourProbe*` or `FiveProbe*` are forbidden in the R2.68 public model.

## Correct-parent reuse

R2.68 reuses corrected R2.67.1 primitives where semantics are already trusted: positional schema canonicalization, intervention enumeration/validation, finite-value normalization, expression evaluation and DSL semantics, subset-specific free-field recomputation, public collision detection, and attempted-observation accounting.

## Proposal and validation search

Search basis sizes in increasing cardinality. For each legal basis:

1. build discovery-only composition examples from selected probes plus basis-specific free fields;
2. if public discovery evidence already contains a target collision under the complete basis exposure, build a `BasisCollisionCertificate` and rule that basis out information-theoretically;
3. otherwise run bounded expression synthesis using discovery examples only;
4. require every selected probe field to occur structurally in the candidate;
5. validate the selected expression on disjoint validation examples;
6. keep search-budget exhaustion or search miss inconclusive unless an information-theoretic collision certificate exists.

Per-basis and global candidate budgets are explicit and deterministic. Validation outputs may not control proposal ordering.

## Local proper-subset necessity authority

`NecessityCertificate` is reserved for a **non-empty proper subset of the selected basis**. Full-basis collision screening is not a necessity certificate.

For selected basis `B` of size `k >= 2`, local proof completeness requires exactly `2^k - 2` proper-subset certificates. For each subset `S`:

- recompute `S`'s own intervention profiles;
- recompute the fields left free by exactly `S`;
- rebuild the complete exposed evidence vector for `S`;
- find a public collision where identical exposed evidence has different normalized targets;
- bind the certificate to selected-basis IDs, subset IDs, subset cardinality, exposed fields, evidence digest and witness digest.

A certificate cannot be minted for the full basis, cannot contain foreign profile IDs, cannot contain duplicate profile IDs, and cannot be replayed under a different exposure schema.

Independent validator #74/#77 identified this authority distinction; canonical tests preserve the proper-subset boundary.

## Global lower-basis proof authority

`BasisCollisionCertificate` is separate from `NecessityCertificate`. It proves that one complete candidate basis of lower cardinality is information-theoretically insufficient under that basis's own full exposed evidence.

Each certificate binds:

- the exact intervention/profile identities of the candidate basis;
- basis cardinality;
- exposed fields;
- canonical public evidence digest;
- proof kind `public_basis_target_collision`;
- witness digest and witness rows.

`AdaptiveCausalBasisStructureReceipt.lower_basis_certificates` carries one replayable certificate for every lower basis counted as certified. `lower_basis_universe_digest` binds lower-basis identity, exposure, status and witness digest. A counter without a corresponding certificate is not sufficient for global-minimality authority.

Global proof completeness requires:

- every legal lower-cardinality basis is represented in the ledger;
- `lower_basis_certified == lower_basis_count`;
- `lower_basis_inconclusive == 0`;
- every certified lower-basis row has a non-empty replayable witness digest.

## Probe synthesis and terminal authority

After structure selection, each selected intervention receives an executable probe expression synthesized from discovery evidence and checked on validation intervention outputs.

Terminal authority then re-observes the exact selected interventions on independent terminal contexts before evaluating the final composed expression.

Terminal base contexts and terminal intervention contexts must be semantically disjoint from all earlier oracle query inputs. Any overlap, invalid context, oracle exception, non-finite result, probe mismatch or final mismatch fails closed with zero false terminal accepts.

## Exact attempted-observation accounting

Every receipt counter represents work actually attempted, never planned denominators.

- Pre-oracle context rejection or evidence-overlap rejection does **not** increment an observation counter.
- An oracle call that is actually attempted is counted even if it raises or returns an invalid value.
- Probe and final exact counters increment only after successful exact comparison.

Explicit terminal failure states include:

- `terminal_probe_evidence_overlap`
- `terminal_probe_context_rejected`
- `terminal_probe_oracle_error`
- `terminal_probe_validation_failed`
- `final_terminal_oracle_error`
- `final_validation_failed`

Independent hosted RED→GREEN accounting tests freeze these semantics.

## Other fail-closed states

The public receipt also distinguishes at least:

- `adaptive_basis_discovered`
- `sufficient_but_minimality_inconclusive`
- `necessity_certificate_missing`
- `basis_search_budget_exhausted`
- `probe_synthesis_failed`
- `probe_validation_failed`
- `no_adaptive_basis`

Malformed evidence, certificate inconsistency or authority-ledger incompleteness cannot be promoted as minimality.

## Phase-A benchmark

`benchmarks/kfigg/r268_adaptive_causal_basis.py` freezes four roles:

1. **one-probe nuisance rejection** — irrelevant target-preserving intervention rejected; expected selected basis size `0` and `passed == false`;
2. **two-probe positive family** — certified sufficient and globally minimal basis size `2`;
3. **three-probe positive family** — certified sufficient and globally minimal basis size `3`;
4. **four-probe positive family** — certified sufficient and globally minimal basis size `4`.

The authored benchmark therefore expects:

- `selected_basis_sizes == [0, 2, 3, 4]`;
- `adaptive_selected_basis_sizes == [2, 3, 4]`;
- complete lower-basis ledgers `[0, 2, 6, 14]`;
- replayable lower-basis certificates for every positive case;
- complete proper-subset necessity certificates for every positive case;
- exact validation/terminal accounting;
- zero false accepts;
- `trainable_parameter_count == 0`.

Required adversarial properties include nuisance rejection, finite-equivalent intervention preservation, validation-independent proposal ordering, field permutation invariance, disjoint composition holdout, lower-order search-miss inconclusiveness, proper-subset certificate binding, global certificate replay, terminal disjointness, pre-oracle accounting, invalid-oracle fail-closed behavior and deterministic replay.

## External transfer

External evidence is a separate hosted gate using pinned NumPy `2.4.6` and callable I/O only. External source internals are not exposed to the solver.

External success cannot override a failed core authority gate. Final external evidence must be regenerated on the frozen accepted-parent R2.68 source after production stops changing.

## TDD and independent challengers

TDD is mandatory for production corrections. Hosted RED evidence is retained when available, and independently opened challenger PRs remain useful even when their code is not merged.

Canonical regressions include defects found by independent workers around:

- composition holdout leakage (#75);
- proper-subset certificate authority (#74/#77);
- target-preserving nuisance probes;
- attempted-observation accounting;
- validation-distinct/finite-equivalent intervention universe collapse.

## Promotion boundary

R2.68 may be called `ACCEPTED_BOUNDED_CAPABILITY` only after:

- exact accepted R2.67.1 ancestry is fixed;
- production source/protocol is frozen before final evidence measurement;
- authored evidence recomputes from the frozen source;
- pinned I/O-only external transfer passes on the same source;
- Python 3.11 and 3.13 focused verification pass;
- protected parent lineage passes;
- independent proof/accounting challengers are resolved or explicitly adjudicated;
- Nolane World adjudication is recorded without forcing convergence;
- exact source/test/evidence hashes are recorded;
- release bundle is generated from the frozen tree;
- post-merge exact-main verification passes.

No readiness score automatically increases merely because a bug was fixed or a receipt became internally consistent.

## Non-claims

R2.68 does not establish open-ended causal language invention, unbounded intervention cardinality, stateful/temporal experimentation, unrestricted scientific autonomy, broad software-engineering autonomy, human-level reasoning, frontier-model parity, or AGI.

It establishes a bounded architecture for discovering, validating and proof-scoping a variable-cardinality causal intervention basis while refusing to treat search failure, finite-evidence collapse, validation leakage, answer-copy shortcuts or unverifiable counters as proof.
