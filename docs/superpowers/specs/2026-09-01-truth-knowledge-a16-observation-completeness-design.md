# A16 — Observation Completeness / Missingness Truth v10

## Status

Design checkpoint for External Core family A. This document does not accept A16. Acceptance requires test-first RED→GREEN proof, fresh exact-head Truth A CI, intended Family-A diff review, merge-state Refoundation proof, latest-main race guard, expected-head production merge, and a separate acceptance seal.

## Problem

A1–A15 make truth dependency-scoped, relation-aware, temporal, provenance-bound, multi-justified, defeasible, source-dependence-aware, and explicitly context-qualified. They still reason only over evidence and claims that already exist.

That leaves a distinct epistemic defect: the system cannot canonically represent an observation that was required but never produced usable evidence. An evidence set can therefore be authentic, temporally valid, context-applicable, independent, and still be selectively incomplete.

Examples include:

- 1,000 cases were required but telemetry retained only 600;
- a required audit sample timed out;
- a sensor was unavailable during a decision-critical window;
- a verifier reports only successful checks and omits attempted failures;
- a measurement was censored or invalidated by observation interference.

The absence of an Evidence record is not itself evidence of absence. Missingness must be represented before Assurance may treat coverage as complete.

## Scope boundary

A16 is deliberately narrow. It does not build a sensor runtime, telemetry scheduler, experiment engine, causal inference system, or task planner. Family A only owns the canonical truth-maintenance semantics required to answer:

1. what observations were required for a claim;
2. what the current append-only result of each required observation is;
3. whether a v10 epistemic scope is complete enough to support verification and closure.

Execution of observations remains outside Family A.

## Binding

A16 introduces the exact binding mode:

`observation-context-dependence-defeasible-justification-provenance-lineage-temporal-v10`

Historical v1–v9 modes remain exact historical protocols and are not reinterpreted.

## Authority law

A16 adds sidecars only and preserves exactly five canonical Family-A authorities.

- `knowledge_observation_truth.py` declares `PARENT_COMPONENT_ID = "external.knowledge"`.
- `evidence_observation_truth.py` declares `PARENT_COMPONENT_ID = "external.evidence"`.
- `epistemic_observation_truth.py` declares `PARENT_COMPONENT_ID = "external.epistemic"`.
- `verification_observation_truth.py` declares `PARENT_COMPONENT_ID = "external.verification"`.
- `assurance_observation_truth.py` declares `PARENT_COMPONENT_ID = "external.assurance"`.

No A16 sidecar may define `COMPONENT_ID`.

## Canonical observation requirement

`ObservationRequirement` is an immutable content-addressed slot owned by the Knowledge sidecar. It binds:

- exact `claim_id`;
- exact immutable `KnowledgeClaim.content_digest`;
- explicit `observation_id`;
- required `EvidenceChannel`;
- canonical requirement digest.

An observation ID is unique within a claim requirement revision. A requirement cannot be rebound to another claim, claim content digest, or channel without creating a new requirement-set revision.

One slot means one required observation outcome. If a policy needs N observations, it declares N distinct observation IDs. A16 does not invent probabilistic sample-size policy.

## Requirement-set revision and registry

`ObservationRequirementSetRevision` binds one claim to a canonical sorted tuple of `ObservationRequirement` rows plus strict revision number, predecessor digest after revision 1, exact claim content digest, and canonical revision digest.

`ObservationRequirementRegistry` is append-only and enforces revision 1 then exact +1, predecessor integrity, exact claim/content binding, unique observation IDs per revision, deterministic ordering/restore, and relevant-only projection.

A claim with no requirement-set revision is legacy observation-unconstrained. Projection encodes that explicitly as `unconstrained`, so adding a future requirement revision stales a v10 scope that depended on the earlier unconstrained state.

## Observation result semantics

`ObservationOutcome` has exactly these values:

- `OBSERVED` — usable Evidence exists and is bound to the requirement;
- `MISSING` — the required observation was expected but no result was obtained;
- `CENSORED` — a result existed or may have existed but cannot be treated as unbiased/complete evidence;
- `UNAVAILABLE` — the observation mechanism was unavailable;
- `TIMEOUT` — the attempt ended without a determinate result;
- `INTERFERED` — the observation process is known to have materially changed or invalidated the measured condition.

All outcomes except `OBSERVED` are epistemically incomplete. None may silently become `REFUTED`, `SUPPORTED`, or negative evidence.

## Observation result revision and ledger

`ObservationResultRevision` is append-only per requirement digest and binds exact `ObservationRequirement.digest`, exact requirement claim identity/content/channel, strict result revision number, predecessor digest after revision 1, outcome, optional exact `TruthEvidence.evidence_id` and `content_digest` only for `OBSERVED`, explicit non-empty reason for every non-`OBSERVED` outcome, and canonical digest.

Rules:

1. `OBSERVED` requires exact Evidence.
2. Observed Evidence must have `subject_id == requirement.claim_id` and the same `EvidenceChannel`.
3. Non-`OBSERVED` outcomes must not carry Evidence IDs or content digests.
4. A timeout/missing/censored/unavailable/interfered result may later be superseded by a new append-only revision, but history is never erased.
5. Same revision rebinding, predecessor mismatch, requirement rebind, and Evidence content mismatch fail closed.
6. An Observation result never creates or mutates `TruthEvidence`.

`ObservationResultLedger` exposes deterministic current status, history, relevant-only projection, digest, and tamper-evident restore.

## v10 epistemic scope

`ObservationTruthScope` wraps the exact accepted v9 `ContextTruthScope`; it does not reinterpret v9.

It binds exact v9 audit/context scope, the observation-requirement projection for exact v9 `lineage_claim_ids`, the observation-result projection for those requirements, required observation IDs/digests, incomplete observation IDs partitioned by outcome, observation completeness debts, and canonical v10 digest.

`ObservationEpistemicJudge` first recomputes canonical v9 state with `ContextEpistemicJudge`, then computes observation completeness only over the target lineage.

### Reachability law

Observation requirements relevant to target closure are exactly those attached to `ContextTruthScope.lineage_claim_ids`. Same-key competitors that exist only in `scope_claim_ids` remain visible in the v9 audit state but do not create target observation debt merely by being competitors. This prevents an unrelated or losing competitor from vetoing the target through its own missing observations.

Unrelated claim requirement/result revisions do not stale the target.

### Disposition law

A16 does not manufacture support/refutation from observation bookkeeping.

- If the v9 target disposition is not `SUPPORTED`, v10 preserves it and records observation state for audit.
- If v9 says `SUPPORTED` but a required observation on the exact target lineage is not `OBSERVED`, v10 target disposition becomes `UNKNOWN`.
- The underlying v9 disposition remains available in `audit_context_scope` for historical/audit inspection.

This prevents a structurally supported claim from being promoted when required coverage is incomplete.

### Debt law

Each incomplete lineage requirement emits an `EpistemicDebt` bound to the owning claim and exact observation ID. Canonical reasons are:

- `required_observation_missing`;
- `required_observation_censored`;
- `required_observation_unavailable`;
- `required_observation_timeout`;
- `required_observation_interfered`;
- `required_observation_unrecorded` when no result revision exists.

These debts are critical for target closure. Requirements on claims outside `lineage_claim_ids` are audit-visible only and cannot veto the target.

## Verification v10

A16 uses dedicated v10 receipt/coverage/ledger. v9 receipts cannot masquerade as v10.

`ObservationTruthVerificationReceipt` binds exact v10 scope digest, exact TruthContext and TemporalContext identity inherited from v10 scope, exact observation-requirement/result projection digests, verifier Evidence/context/provenance/dependence state retained from v9, and canonical digest.

Receipt validity requires the v10 scope to be current. A verifier cannot restore completeness merely by being independent or by using a different channel.

Independence semantics remain exactly A14/A15: context and observation IDs are applicability/coverage state, not independence keys. Negative receipts remain retained.

## Assurance v10

A16 uses a dedicated v10 closure certificate and gate. v9 certificates cannot masquerade as v10.

The gate recomputes canonical v10 scope live. Closure requires all accepted A15 conditions plus target v10 disposition supported, no critical observation debt on the exact target lineage, exact current observation-requirement/result projections, and v10 verification coverage bound to the same scope.

A certificate becomes stale when a relevant lineage requirement-set revision or observation-result revision changes. Unrelated observation changes do not stale it.

## Compatibility

With an empty `ObservationRequirementRegistry`, an empty `ObservationResultLedger`, and otherwise identical inputs, v10 must reproduce v9 target disposition, scope membership, verification independence/channel coverage, and assurance closure behavior.

A16 is additive and must not rewrite any v1–v9 serialized protocol.

## Required regressions

1. A claim with no observation requirements reproduces v9 behavior.
2. A required `OBSERVED` slot with exact matching Evidence permits the v9 supported state to remain supported.
3. A required slot with no result becomes `UNKNOWN` with `required_observation_unrecorded` debt.
4. `MISSING` becomes `UNKNOWN` + missing debt, never refutation.
5. `TIMEOUT` becomes `UNKNOWN` + timeout debt, never refutation.
6. `CENSORED`, `UNAVAILABLE`, and `INTERFERED` each remain incomplete and produce distinct debt.
7. `OBSERVED` without Evidence is rejected.
8. Non-observed outcome carrying Evidence is rejected.
9. Observed Evidence with wrong claim or channel is rejected.
10. Requirement revision sequence/predecessor/rebind attacks are rejected.
11. Observation result sequence/predecessor/requirement/evidence-digest rebind attacks are rejected.
12. Relevant lineage requirement/result revision stales v10 scope/receipt/certificate.
13. Unrelated requirement/result revision does not stale target scope/certificate.
14. A same-key competitor outside `lineage_claim_ids` cannot veto target closure through missing observations.
15. Missing/censored result cannot mint verification independence.
16. v9 receipt/certificate cannot masquerade as v10.
17. All five A16 sidecars preserve the five-authority law and define no `COMPONENT_ID`.
18. Serialization rejects unexpected fields and duplicate revisions.
19. Empty observation state reproduces v9 compatibility.

## Acceptance gate

A16 is accepted only after focused RED evidence, GREEN implementation/hardening, fresh Python 3.11/3.13 Truth A exact-head CI plus repository audit, intended Family-A-only diff and clean review surface, fresh synthetic full Refoundation merge-state proof, latest-main race guard, expected-head production merge, separate docs-only acceptance seal, seal Truth + Refoundation proof, expected-head seal merge, and post-merge canonical verification.
