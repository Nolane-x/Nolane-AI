# Truth / Knowledge A16 Candidate — Observation Completeness / Missingness Truth v10

## Status

**CANDIDATE — NOT ACCEPTED.**

This record describes the A16 implementation candidate. It does not promote A16 to canonical production status. Production acceptance still requires a clean latest-main integration, fresh exact-head Truth A proof, full Refoundation merge-state proof, race guard, expected-head production merge, and a separate acceptance seal.

## Scope

A16 is restricted to Family A: Evidence, Knowledge, Epistemic, Verification, and Assurance. It preserves exactly five canonical Family-A authorities and adds no sixth authority.

Canonical v10 binding mode:

`observation-context-dependence-defeasible-justification-provenance-lineage-temporal-v10`

A16 represents required observations and their append-only outcomes so missing, censored, unavailable, timed-out, or interfered observations cannot be silently treated as negative evidence or complete assurance.

Observation obligations apply only to the exact v9 target lineage (`lineage_claim_ids`). Competitors that exist only in the relation-aware audit scope do not create observation debt for the target.

## Architecture

### Knowledge

`nolane.external_core.knowledge_observation_truth`

- immutable `ObservationRequirement` slots;
- append-only `ObservationRequirementSetRevision`;
- strict `ObservationRequirementRegistry`;
- exact claim/content/channel binding;
- explicit `unconstrained` projection for legacy claims.

### Evidence

`nolane.external_core.evidence_observation_truth`

- outcomes: `OBSERVED`, `MISSING`, `CENSORED`, `UNAVAILABLE`, `TIMEOUT`, `INTERFERED`;
- append-only `ObservationResultRevision` and `ObservationResultLedger`;
- only `OBSERVED` may bind Evidence;
- exact immutable requirement snapshot and Evidence content digest;
- non-observed outcomes are incomplete, never support/refutation.

### Epistemic

`nolane.external_core.epistemic_observation_truth`

- wraps the exact accepted v9 `ContextTruthScope` as immutable audit state;
- computes observation completeness only over exact target lineage;
- a v9-supported target with incomplete required observation becomes v10 `UNKNOWN`, never `REFUTED`;
- emits outcome-specific critical observation debt;
- unrelated observation mutations do not stale the target.

### Verification

`nolane.external_core.verification_observation_truth`

- dedicated v10 receipts and coverage;
- binds exact v10 scope, TruthContext, TemporalContext, observation requirement/result projections, Evidence/context/provenance/dependence state;
- preserves A14/A15 controller/common-basis independence semantics exactly;
- observation identity and context never mint independence;
- negative receipts remain retained;
- v9 receipts cannot masquerade as v10.

### Assurance

`nolane.external_core.assurance_observation_truth`

- dedicated v10 closure certificate and gate;
- recomputes canonical v10 state live;
- preserves accepted risk thresholds: LOW/STANDARD 1 source + 1 channel; HIGH 2 + 2; CRITICAL 3 + 3;
- incomplete observation blocks closure with explicit observation reasons;
- relevant observation revisions stale certificates; unrelated revisions do not;
- v9 certificates cannot masquerade as v10.

## Five-authority invariant

The five A16 sidecars bind only these existing parents:

1. `external.evidence`
2. `external.knowledge`
3. `external.epistemic`
4. `external.verification`
5. `external.assurance`

Every A16 sidecar exposes `PARENT_COMPONENT_ID` only and must not define `COMPONENT_ID`.

## TDD proof chain

- Requirement RED: commit `3f8725293c82510e22d12394b27333a6f5753429`, Truth #180 — clean missing `knowledge_observation_truth` capability.
- Requirement GREEN: Truth #181 — Python 3.11/3.13 and repository authority audit GREEN.
- Observation-result RED: commit `2977885326fff6c47610dd569f821be0faaad598`, Truth #182 — clean missing `evidence_observation_truth` capability.
- Observation-result GREEN: commit `871bdc1e01725cc4aae4e4b064012371d72c9f0a`, Truth #183 — Python 3.11/3.13 and audit GREEN.
- Epistemic-scope RED: commit `2f339cb04a57ba64f5a9e39b6ef6c38464eb3dc9`, Truth #184 — clean missing `epistemic_observation_truth` capability.
- Epistemic-scope GREEN: commit `02aad62628c7a42eb4b0c8c95c10d1f9c31634f0`, Truth #185 — Python 3.11/3.13 and audit GREEN.
- Verification RED: commit `a49f5a221c5c6c8ec9f17f634a7c15b7b6056b92`, Truth #186 — clean missing `verification_observation_truth` capability.
- Verification GREEN: commit `b187c9cda85c5cfdb333f7475e1142661b252eb2`, Truth #187 — Python 3.11/3.13 and audit GREEN.
- Assurance RED: commit `bb4a5d35d9a32567b7b10f6df684756c4868cf8f`, Truth #188 — clean missing `assurance_observation_truth` capability.
- Assurance GREEN: exact implementation commit `fcdc60a5ee55119a0e97444ef3a75fa99d8570eb`, Truth #189 — Python 3.11/3.13 and audit GREEN.
- Assurance binding proof: commit `049f37b2892a9d2df46e75a9f62791d1610c142e`, Truth #190 — Python 3.11/3.13 and audit GREEN.
- Five-authority hardening: commit `0a8b2e41ea6713eec282e452077eb658dafe7f1b`, Truth #191 — GREEN.
- Empty-state v9 compatibility hardening: commit `9945f0a9949c2cbf027be845f370b5755a9761a2`, Truth #192 — superseded for acceptance by the final exact-head gate, which reruns the same contracts.
- Protocol restore/tamper hardening: commit `fee62d32a4b567a64458da78502f6fa2e3c1fa38`, Truth #193 — superseded for acceptance by the final exact-head gate, which reruns the same contracts.

## Candidate acceptance gate

The candidate head must still prove all of the following before integration:

- compile all canonical A authorities and A1–A16 / v1–v10 sidecars;
- all `tests/test_truth_knowledge_*.py` GREEN on Python 3.11 and 3.13;
- repository authority audit GREEN on the same immutable head;
- exact five-authority invariant;
- empty observation state reproduces v9 epistemic, verification, and assurance behavior;
- protocol downgrade, projection tamper, duplicate restore, and cross-version masquerade attacks fail closed.

After that, A16 must be rebuilt directly on the latest `main`, preserving all concurrent specialist work, and pass full merge-state validation before production merge.
