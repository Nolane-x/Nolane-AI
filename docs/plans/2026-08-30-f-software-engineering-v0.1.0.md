# F. Software Engineering — Governed Engineering Control Architecture

Date: 2026-08-30  
Status: as-built implementation candidate  
Implementation line: closure `0.1.x`, policy `0.2.x`, validity `0.2.x`, unified control `0.4.x`  
Scope: `Coding Claims`, `Coding Patches`, `Coding Control`, `Debugging`, `UI/UX`

## 1. Architectural position

Epoch 0 already gives Nolane AI five canonical F authorities:

- `external.coding.claims` — source mutation scope and conflict authority;
- `external.coding.patches` — patch identity and patch-ledger authority;
- `external.coding.control` — coding assignment/readiness authority;
- `external.debugging` — failure reproduction/root-cause/resolution authority;
- `external.ui_ux` — UI/UX observation and readiness authority.

This work does **not** create a sixth canonical F authority. The `software_engineering*` modules are cross-surface composition/control protocols. Their internal identifiers are intentionally absent from the canonical component implementation ledger. Canonical write authority remains with the five existing F components.

The composition plane exists because local green receipts are insufficient to prove an engineering change is safe to hand off. A change can become stale after verification, evidence can be revoked, mutation authority can disappear between precondition check and apply, Debug/UI receipts can point at a different lineage, and caller-selected verification requirements can under-specify risk.

## 2. Nolane World mechanisms adapted into F

Nolane World 0.12.0 is used as a reasoning source, not imported as a runtime dependency.

| Nolane World principle | F implementation | Result |
| --- | --- | --- |
| dependency/provenance graph | `EngineeringEvidenceLedger` | evidence invalidation cascades instead of silently leaving stale proof live |
| explicit action lifecycle | `PatchTransactionLedger` | patch existence is separated from patch mutation and outcome |
| validate-before-publish | governed closure + policy gate | no candidate-ready state before postconditions close |
| least authority | `candidate_only` / `mutation_scope_only` | F cannot self-promote into release, Assurance or capability authority |
| reversible action | rollback artifact + rollback terminal state | every mutation transaction declares recovery before application |
| current truth vs history | historical closure + current-validity receipts | immutable history is not confused with present validity |
| state-bound authority | immutable claim-state binding | exact mutation permission at action time is provable later |
| fail-closed capability | mutation authority receipt consumption | apply cannot bypass explicit current authorization |

## 3. The final F control stack

The implemented stack is intentionally layered:

```text
Canonical F Authorities
  ├─ Coding Claims
  ├─ Coding Patches
  ├─ Coding Control
  ├─ Debugging
  └─ UI/UX
          │
          ▼
Engineering Change Manifest
          │
          ▼
Historical Claim-State Binding
          │
          ▼
Engineering Evidence Graph
          │
          ▼
Patch Transaction
          │
          ├─ precondition evidence
          ├─ mutation authority receipt
          ├─ receipt consumption
          ├─ apply
          ├─ outcome observation
          └─ postcondition evidence
          │
          ▼
Risk/Surface-Derived Verification Policy
          │
          ▼
Canonical Upstream Receipt Integrity Boundary
          │
          ▼
Cross-Surface Engineering Closure
          │
          ▼
CANDIDATE_READY / candidate_only
          │
          ▼
Current Validity Revalidation
```

### 3.1 Evidence graph

`EngineeringEvidenceAttestation` is content-addressed and binds:

- subject reference and exact canonical subject digest;
- patch producer;
- independent verifier;
- verifier region;
- evidence kind;
- pass/fail outcome;
- concrete evidence refs;
- exact source revision;
- environment digest;
- upstream dependency refs.

Successful self-verification is rejected. Successful engineering evidence requires `verification-testing` authority.

Evidence revocation is historical, not destructive. Revoking an upstream dependency recursively invalidates all dependent engineering attestations while retaining the evidence history.

### 3.2 Patch transaction state machine

Lifecycle:

`PROPOSED -> CLAIMS_BOUND -> PRECONDITIONS_VERIFIED -> APPLIED -> OUTCOME_OBSERVED -> POSTCONDITIONS_VERIFIED -> CANDIDATE_READY`

Failure exits:

- `QUARANTINED`
- `ROLLED_BACK`

Important invariants:

1. Every non-proposed transaction has explicit source claims.
2. Preconditions are exact-patch/exact-source attestations.
3. Rollback material is declared before mutation.
4. Applied effects require outcome evidence.
5. Postconditions require valid independent attestations.
6. Candidate-ready requires a closure receipt.
7. Rollback is terminal for candidate readiness.

## 4. Historical authorization vs current mutation authority

The architecture deliberately separates two facts that must not be conflated.

### Historical authorization

`EngineeringClaimBindingLedger` freezes the exact mutation authority observed before apply:

- claim ID;
- agent;
- task;
- file scope;
- symbol scope;
- directory scope;
- claim mode;
- status;
- canonical claim-state digest.

This immutable snapshot proves that the mutation was authorized at the time it happened.

### Current mutation authority

A different receipt answers whether mutation is allowed **now**.

`EvidenceBoundMutationAuthorityEngine` requires all of the following at the pre-apply instant:

- transaction is exactly `PRECONDITIONS_VERIFIED`;
- bound claims still match their historical state;
- bound claims remain active exclusive-write claims;
- bound claims cover the exact current patch scope;
- exact patch digest/transaction lineage matches;
- every precondition attestation is still live and unrevoked.

Application is a two-step capability flow:

`assess_mutation_authority(patch) -> authorized receipt -> mark_applied(..., receipt_id)`

`mark_applied` cannot be called through the unified F control plane without consuming a known authorized receipt. It also rechecks live claim/evidence state at consumption time, so authority can be revoked between assessment and application.

## 5. Normal lease release does not poison completed engineering evidence

A claim/lease is transient permission to mutate. It is **not** permanent quality evidence.

Therefore:

- releasing a claim before apply revokes mutation authority;
- releasing a claim after successful apply is normal lifecycle;
- post-apply candidate closure uses the historical claim-state binding;
- current candidate validity does not become stale merely because the lease was normally released.

This prevents a semantic bug where a completed, independently verified patch would become invalid simply because its write lease was cleaned up correctly.

## 6. Change manifest and policy-derived verification floor

`EngineeringChangeManifest` binds exact patch/source scope, dependency refs, impacted components, risk class and inferred sensitive surfaces.

The caller does not choose a weak verification set. `EngineeringVerificationPolicy` derives the minimum evidence family:

- all patches: compile + test + static;
- UI-sensitive: visual + responsive + accessibility + interaction;
- security-sensitive: security;
- performance-sensitive: performance;
- debug-origin: reproduction + root cause;
- high/critical risk: independent review.

UI/security/performance sensitivity can be inferred from touched files/symbols and can also be declared conservatively. Declared risk can raise the floor but cannot reduce inferred risk.

## 7. Cross-surface receipt integrity

The unified F control boundary does not trust a Python object merely because it has fields named `ready`, `digest` or `receipt_id`.

Before cross-surface closure, canonical Coding/Debug/UI receipts are round-tripped through their own canonical state codecs. This detects direct construction with forged digest/state.

Positive Coding readiness is additionally rejected if it is internally impossible, including:

- `ready=True` with non-empty reasons;
- failed verification;
- non-zero false accepts;
- non-zero regressions.

Positive UI readiness requires clean reasons plus observation and quality-evidence identities.

This is a confused-deputy defense at the F composition boundary; upstream components retain semantic ownership of how their receipts are produced.

## 8. Cross-surface closure

A candidate closure binds:

- exact patch ID and canonical patch digest;
- patch transaction;
- exact source revision;
- Coding Readiness receipt and digest;
- required independent engineering attestations;
- optional Debug resolution lineage;
- optional UI readiness lineage;
- historical claim binding;
- policy-derived verification requirements.

For debug-origin work, Debug resolution must point to the same patch and Coding Readiness receipt.

For UI-sensitive work, UI readiness must be green and point to the same patch and Coding Readiness receipt.

The positive terminal output is exactly:

- decision: `CANDIDATE_READY`;
- authority: `candidate_only`.

It cannot claim release, deployment, Capability Acquisition promotion, Assurance acceptance or repository canonical status.

## 9. Immutable history vs current candidate validity

An engineering closure is historical evidence: “this candidate satisfied F closure at this source/evidence state.” It is never rewritten after the fact.

`EngineeringValidityEngine` produces a separate content-addressed current-validity view. A historical ready candidate becomes stale when, for example:

- current source revision differs;
- current patch serialization differs;
- transaction/closure lineage changes;
- an attestation or upstream dependency is revoked.

A normal post-apply lease release alone is not a technical invalidation event.

This implements the Nolane World distinction between immutable provenance history and mutable present validity.

## 10. Unified control plane and deterministic restore

`SoftwareEngineeringControlPlane` is the recommended F composition entry point. It unifies:

- work record;
- change manifest;
- evidence ledger;
- patch transaction ledger;
- claim-state binding ledger;
- verification policy;
- mutation-authority history;
- canonical upstream receipt boundary;
- governed gate;
- closure history;
- current-validity history.

Its snapshot is content-addressed. Restore revalidates cross-layer lineage rather than merely deserializing values.

Adversarial restore tests recompute inner and outer digests after tampering and still require rejection when work↔manifest, gate↔closure or other cross-layer identities no longer agree.

## 11. Authority boundary with the rest of Nolane AI

F may consume D/E identifiers or receipts and may emit candidate evidence to later systems, but it does not own:

- Requirements truth;
- Planning authority;
- Architecture authority;
- Integration acceptance;
- Executor authority outside its bounded patch mutation;
- Candidate Synthesis selection;
- Capability Acquisition promotion;
- Assurance acceptance;
- Evaluation/release authority;
- repository canonical status.

This is particularly important while A/B/C/D/E/G/etc. are being upgraded independently by specialist AIs.

## 12. Canonical component ownership

The canonical implementation ledger remains authoritative. The five F components remain the only canonical F write authorities.

The `external.software_engineering*` identifiers are internal composition/snapshot identities and are intentionally **not** registered as canonical-native components. Tests lock this non-registration so the composition plane cannot silently grow into a shadow canonical authority.

Protocol helpers such as the mutation evidence guard, historical-authorization gate and canonical-receipt boundary deliberately do not declare `COMPONENT_ID`.

## 13. TDD and adversarial verification contract

The implementation has been built in repeated RED -> implementation -> GREEN cycles covering, among others:

- independent content-addressed evidence;
- self-verification rejection;
- evidence dependency revocation;
- transaction lifecycle and rollback terminality;
- stale source rejection;
- Debug/UI cross-lineage closure;
- deterministic receipt identity;
- snapshot forgery detection;
- exact bound-claim scope rather than agent-wide claim borrowing;
- live candidate revalidation;
- normal post-apply claim release semantics;
- policy-derived verification floors;
- mutation-authority revocation before apply;
- precondition-evidence revocation before apply;
- explicit mutation receipt consumption;
- canonical upstream receipt integrity;
- fixed candidate-only authority.

The acceptance workflows are:

1. `Coding AGI Coding Organization Part V` on Python 3.11 and 3.13;
2. `Nolane-AI Refoundation Epoch 0` on Python 3.11 and 3.13;
3. merge-ref verification against current `main` so independently upgraded subsystems are composed, not tested in isolation.

Historical frozen release workflows can remain red for their own frozen-boundary reasons; they are not treated as F success evidence.

## 14. Remaining F-only depth frontier

The architecture now closes the major control/provenance gaps. Future F work should deepen evidence quality rather than widen authority:

- impact graph computed from static/import/runtime dependency analysis instead of declared impacted components;
- differential test-selection proofs tied to symbol coverage;
- mutation budgets and rate/size constraints for high-risk patches;
- security policy profiles richer than path/symbol heuristics;
- performance budgets with baseline distributions and regression confidence;
- root-cause falsifier obligations and counterfactual debugging evidence;
- UI state-machine/path coverage in addition to viewport evidence;
- automatic quarantine/recovery orchestration when a live candidate loses validity;
- cryptographic/external execution provenance when Nolane moves beyond repository-local evidence.

None of these future extensions should grant F promotion or release authority.