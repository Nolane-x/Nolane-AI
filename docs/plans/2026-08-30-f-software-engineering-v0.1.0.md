# F. Software Engineering — Governed Closure Plane v0.1.0

Date: 2026-08-30
Status: implementation candidate
Scope: `Coding Claims`, `Coding Patches`, `Coding Control`, `Debugging`, `UI/UX`

## 1. Why this upgrade exists

Epoch 0 already moved all five F surfaces under canonical `nolane.external_core` authority. This change therefore does **not** create another implementation hierarchy and does not reopen migration debt. It adds a cross-surface closure plane that makes existing F outputs mutually accountable before an engineering result can leave F as a candidate.

The previous native components are useful but locally scoped:

- Coding Claims owns source mutation scope and conflict exclusion.
- Coding Patches owns patch identity, touched scope and evidence references.
- Coding Control owns assignment, lease/claim checks and coding readiness.
- Debugging owns reproduction, root-cause hypotheses, coding handoff and resolution.
- UI/UX owns render observations and visual/responsive/accessibility/interaction readiness.

The gap is cross-surface closure: a green receipt can become stale when the source revision changes; a referenced artifact can later be revoked; a patch can be applied before all postconditions are proven; Debug/UI receipts can point at a different lineage unless a final boundary checks them together; and F must not accidentally become a promotion authority for Candidate Synthesis, Assurance, Evaluation or repository release.

## 2. Nolane World mechanisms adapted into F

This design uses Nolane World 0.12.0 as a reasoning source, not as an imported runtime dependency.

| Nolane World mechanism | F adaptation | Why |
| --- | --- | --- |
| Claim/evidence dependencies and stale propagation | `EngineeringEvidenceLedger` + recursive revocation | A test artifact, tool output or upstream attestation can invalidate every dependent engineering proof. |
| QX action lifecycle | `PatchTransactionLedger` | Source mutation becomes an explicit state machine rather than an implicit "patch exists" event. |
| Validate-before-publish transaction discipline | `SoftwareEngineeringClosureEngine` | A patch cannot reach `CANDIDATE_READY` until postconditions and cross-surface lineage close. |
| Trusted evidence lineage | independent `verification-testing` attestations | Passing self-reports do not count as successful engineering evidence. |
| Provenance closure | subject digest + source revision + environment digest + dependencies | Evidence is bound to the exact thing it proves and can become invalid without being deleted. |
| Least authority | terminal authority=`candidate_only` | F can declare engineering closure, but cannot promote capability/release/canonical authority. |
| Rollback-aware actions | mandatory rollback artifact before mutation + terminal rollback state | Application has an explicit recovery path and cannot be silently reclassified as ready after rollback. |

## 3. New canonical composition surface

File: `nolane/external_core/software_engineering.py`

Component: `external.software_engineering`
Version: `0.1.0`

This is an additive composition surface. It imports only canonical digest authority and consumes existing canonical F receipts by contract. Existing historical bridges and `0.0.1` component ownership remain intact.

### 3.1 Engineering Evidence Ledger

Each `EngineeringEvidenceAttestation` is content addressed and binds:

- exact patch/reference;
- canonical subject digest;
- producer;
- independent verifier and verifier region;
- evidence kind;
- pass/fail outcome;
- concrete evidence references;
- exact source revision;
- environment digest;
- upstream provenance dependencies.

A successful attestation is rejected if verifier equals producer or the verifier is outside `verification-testing`.

Revocation is graph-like rather than destructive. Revoking an upstream dependency recursively marks dependent attestations invalid, preserving the historical record while preventing stale proof from satisfying a new closure gate.

### 3.2 Patch Transaction Ledger

Lifecycle:

`PROPOSED -> CLAIMS_BOUND -> PRECONDITIONS_VERIFIED -> APPLIED -> OUTCOME_OBSERVED -> POSTCONDITIONS_VERIFIED -> CANDIDATE_READY`

Failure exits:

- `QUARANTINED`
- `ROLLED_BACK`

Invariants:

1. Mutation cannot start without explicit source claims.
2. Preconditions must be valid attestations for the exact patch digest and source revision.
3. Applying a patch requires a rollback artifact already named at transaction creation.
4. Applied effects must have observed outcome evidence.
5. Postconditions must be independently attested.
6. Candidate readiness is legal only from postcondition-verified state.
7. A rolled-back transaction cannot later be relabeled candidate-ready.

This state machine deliberately stops before deployment, release, capability promotion or canonical repository mutation authority.

### 3.3 Software Engineering Closure Engine

The closure engine binds one coherent engineering candidate across all F surfaces.

Required base lineage:

- patch canonical digest;
- transaction patch digest;
- current source revision;
- Coding Readiness receipt;
- independent coding verifier;
- valid postcondition attestations;
- source-claim-bound transaction;
- rollback boundary.

Optional domain closures become mandatory when the work declares them:

- Debug work: `DebugResolutionReceipt` must point to the same patch and Coding Readiness receipt.
- UI work: `UIReadinessReceipt` must be ready and point to the same patch and Coding Readiness receipt.

Positive output is exactly:

- decision: `CANDIDATE_READY`
- authority: `candidate_only`

It is intentionally impossible for this layer to claim `promoted`, `released`, `accepted capability`, or `canonical authority`.

## 4. Upgrade effect by F surface

### Coding Claims

Claims are no longer merely an executor-side permission check. They become a required transaction precondition. Mutation history can therefore be audited as "which declared ownership allowed this exact patch transaction?"

Future compatible extension: bind claim-state digests and lease epochs directly, so a released/superseded claim invalidates an unexecuted transaction before application.

### Coding Patches

Patch existence is separated from patch application. A patch now participates in an explicit reversible transaction bound to exact source revision and canonical patch digest. Evidence about a previous patch serialization or previous repository revision cannot silently prove the current candidate.

### Coding Control

Existing `CodingReadinessReceipt` remains authoritative for coding-local readiness. The new closure plane consumes it and adds evidence freshness, transaction postconditions and optional Debug/UI closure. This avoids rewriting Coding Control while making its output safer to compose.

### Debugging

Existing deterministic reproduction/root-cause mechanics remain canonical. For debug-originated patches, F closure requires the final Debug resolution to point to the exact same patch and Coding Readiness receipt. A debug case cannot be considered engineering-closed using a green receipt from another patch lineage.

### UI/UX

Existing visual/responsive/accessibility/interaction evidence remains canonical. When UI closure is required, the final UI readiness must be green and must point to the exact same patch and Coding Readiness receipt. Render/quality work therefore cannot be detached from the source mutation it validates.

## 5. Cross-subsystem authority boundaries

F may consume identifiers/receipts from D/E and may emit a candidate for later systems, but F does not own:

- Requirements truth;
- Planning graph authority;
- Architecture graph authority;
- Executor permission outside its mutation transaction;
- Candidate Synthesis selection/promotion;
- Capability Acquisition promotion;
- Assurance acceptance;
- Evaluation/release claims;
- repository canonical status.

This prevents a "shadow authority" problem while allowing F to become much stricter internally.

## 6. TDD verification contract

The first branch commit adds RED tests before production implementation. The focused suite requires:

1. content-addressed independent evidence;
2. no successful self-verification;
3. explicit patch transaction lifecycle;
4. rollback terminality;
5. stale source revision rejection;
6. recursive provenance revocation;
7. Debug/UI lineage closure when declared;
8. deterministic closure receipts independent of attestation input order;
9. terminal authority fixed to `candidate_only`.

The existing coding organization workflow exercises Python 3.11 and 3.13 plus prior organization regressions. The Refoundation workflow additionally guards canonical-native repository constraints.

## 7. What v0.1.0 deliberately does not claim

This implementation is an engineering-control architecture upgrade. It does not establish arbitrary real-world software-engineering competence, external benchmark superiority, autonomous production deployment safety, or AGI. Those remain evidence/release questions owned by their respective evaluation and assurance authorities.

## 8. Next depth frontier after this closure

The next F-only iteration should deepen rather than widen authority:

- exact claim-state/lease epoch binding;
- dependency/blast-radius manifests per patch;
- differential test selection receipts tied to changed symbols;
- mutation budgets and risk classes;
- automatic quarantine on newly revoked evidence;
- root-cause falsifier obligations before debug acceptance;
- UI state-transition coverage, not only screenshot/viewports;
- security/performance policy profiles based on touched surfaces;
- deterministic snapshot restore tests for the complete F closure plane.

These remain inside F and should continue to terminate at candidate authority only.
