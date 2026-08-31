# CURRENT — F. Software Engineering

Date: 2026-08-31
Engineering wave: v1.0.0
Unified control API: `external.software_engineering.control` v0.9.0
Property-evidence protocol: `external.software_engineering.property_evidence` v0.1.0
Property-gate protocol: `external.software_engineering.property_gate` v0.1.0
Effects state protocol: `external.software_engineering.effects` v0.1.0
Effect-fencing protocol: `external.software_engineering.effect_fencing` v0.1.0
Effect-journal protocol: `external.software_engineering.effect_journal` v0.1.0
Effect-recovery protocol: `external.software_engineering.effect_recovery` v0.1.0
Effect-dispatch protocol: `external.software_engineering.effect_dispatch` v0.1.0
Recovery-frontier protocol: `external.software_engineering.recovery_frontier` v0.1.0

F v1.0 extends the crash-consistent v0.9 control plane with property-scoped engineering evidence. A green command, test suite, screenshot, benchmark, reproduction or review is no longer treated as sufficient merely because its evidence kind matches a policy bucket. The verifier must attest an oracle that actually measures the declared engineering property, the witness must bind the exact patch digest and source revision, and the complete required property set must remain live-valid before a terminal candidate receipt can close.

The public control plane advances from v0.8.0 to v0.9.0. The exact v0.8 implementation is frozen in `_software_engineering_control_v08.py`; public v0.9 composes property evidence/gating on the same canonical `EngineeringEvidenceLedger` and includes property state in its content-addressed snapshot. Historical v0.8 state has an explicit migration path through the frozen implementation rather than being interpreted under a rewritten schema.

## Canonical authority

F still has exactly five canonical component authorities:

1. `external.coding.claims`
2. `external.coding.patches`
3. `external.coding.control`
4. `external.debugging`
5. `external.ui_ux`

`software_engineering*` modules remain composition/control protocols. Property obligations have `verification_scope_only`; property witnesses have `evidence_scope_only`; property closures, property gates and property-bound terminal receipts are `candidate_only`. None grants mutation, release, deployment, Assurance acceptance, repository write authority or capability promotion.

## Governed lifecycle

```text
patch + source claims + engineering operation_ref
  -> idempotent attempt initiation / immutable operation lineage
  -> change manifest
  -> immutable claim-state binding
  -> precondition evidence
  -> current mutation-authority receipt
  -> prepare exactly one application intent
  -> durable PRE_DISPATCH marker / coordination_only
  -> external executor boundary
  -> durable observation-only acknowledgement
  -> acknowledgement-backed local finalization
  -> APPLIED + canonical application commit
  -> observe outcome
  -> postcondition evidence
  -> legacy risk/surface verification gate
  -> canonical Coding/Debug/UI receipt integrity
  -> legacy engineering closure / candidate_only
  -> externally supplied required-property manifest
  -> claim-class-specific property obligations
  -> verifier-attested property oracles
  -> exact property witnesses
  -> per-property live closure
  -> complete-set property gate
  -> legacy-closure + property-gate terminal binding
  -> PROPERTY-BOUND CANDIDATE / candidate_only
  -> live evidence re-evaluation can reopen closure
```

The property layer is monotonic: it strengthens terminal eligibility without rewriting the payload/digest semantics of historical Coding, Debug, UI/UX or engineering closure receipts.

## Property evidence model

### Claim classes

The v1.0 property ledger distinguishes the semantic claim being made:

- build integrity;
- functional behavior;
- regression preservation;
- debugging root cause;
- UI visual fidelity;
- UI interaction;
- UI accessibility;
- security property;
- performance property.

Claim classes are not inferred from a generic green command. They identify what must actually be true of the repository/runtime state.

### Proof methods

Supported proof methods include compile/static analysis, unit/integration/property/metamorphic/regression tests, deterministic reproduction, causal probe/bisect, visual diff, responsive/accessibility checks, interaction E2E, security tests and performance benchmarks.

A proof method must be compatible with the underlying canonical `EngineeringEvidenceKind`. Relabeling a TEST attestation as a visual/security/root-cause witness is rejected.

### Oracle binding

A witness declares both `measured_property_ref` and `oracle_ref`.

For a witness to be valid:

- `measured_property_ref` must equal the exact property obligation; proxy labels such as `tests-pass` cannot close a behavioral property;
- `oracle_ref` must be present in the verifier's immutable attestation evidence/dependency lineage;
- the attestation must match the exact patch ref, patch digest and source revision;
- the attestation must remain live-valid and unrevoked;
- proof method and attestation kind must agree.

This blocks property-label laundering: a caller cannot take an unrelated green test and self-declare that it proves a desired semantic property.

### Claim-specific proof floors

- build integrity requires compile evidence;
- functional behavior requires an actual behavioral test family such as integration/property/metamorphic/unit proof bound to the property oracle;
- regression preservation requires regression evidence plus a version-bound baseline;
- debugging root cause requires deterministic reproduction, a causal probe or bisect, and a falsifier witness;
- UI visual fidelity requires visual-diff evidence;
- UI interaction requires interaction E2E evidence; a screenshot/visual diff cannot substitute;
- UI accessibility requires accessibility evidence;
- security requires security evidence and adversarial witness semantics;
- performance requires a benchmark plus a version-bound baseline.

Where an obligation requests multiple independent sources, independence is counted by source family rather than raw witness count so duplicated observations do not manufacture independence.

## Complete-set property gate

A ready individual property closure is not enough to close a patch. The property gate consumes an immutable required-property manifest supplied by the requirements/goal authority and checks the complete set for the exact patch and source revision.

The gate fails closed on:

- missing required obligations;
- unexpected or duplicate closure scope;
- closure/obligation digest mismatch;
- patch or source-revision mismatch;
- stale/revoked underlying attestations;
- a historical closure whose witnesses no longer re-assess ready;
- property-gate or snapshot lineage tampering.

A historical `ready=True` property receipt is therefore not eternal. The gate re-runs the property assessment against the live evidence ledger before minting a current candidate receipt.

The terminal property-bound receipt binds the legacy engineering candidate and the current property gate. It remains `candidate_only`; F still cannot release or deploy.

## Coding / Debugging / UI implications

### Coding claims and patches

The v1.0 property layer does not redefine ownership of Coding Claims or Coding Patches. Patch identity, scope, operation lineage and mutation authority continue to be governed by existing canonical Coding/F mechanisms. Property state is verification-only and cannot authorize mutation.

### Debugging

A root-cause statement cannot close from a reproduction alone. Root-cause property closure requires a discriminating causal probe/bisect and a falsifier witness, so the system distinguishes "I reproduced the failure" from "I established this cause".

### UI/UX

Visual fidelity, accessibility and interaction are separate properties. A visually matching screenshot does not prove keyboard submission, focus behavior, routing, state transition or other interaction semantics. Interaction-sensitive claims require actual interaction E2E evidence.

## Durable dispatch frontier retained from v0.9

All v0.9 crash-consistency invariants remain in force:

- `PRE_DISPATCH` is durable and `coordination_only`;
- dispatch without acknowledgement yields `EXTERNAL_STATUS_REQUIRED` and forbids automatic redispatch;
- F never invents an acknowledgement to escape uncertainty;
- application/rollback acknowledgements are `observation_only`;
- acknowledged application can recover by local finalization without re-invoking the executor;
- rollback still requires independent restored-state verification;
- compatibility backfill is failure-atomic;
- exactly-once claims are limited to local finalization per immutable acknowledged lineage, not distributed exactly-once execution.

## Evidence truth-maintenance

Engineering evidence is content-addressed and revision-bound. Revocation or invalidation never deletes history, but it removes the evidence from current validity. Property closure therefore supports reopening: if an attestation used by a previously green property becomes revoked, stale or lineage-invalid, a fresh assessment becomes blocked and the complete-set property gate refuses current terminal closure.

This follows the same epistemic rule used elsewhere in Nolane: a recorded claim/receipt is historical evidence of what was accepted at that time, not perpetual proof that its premises remain true.

## State and compatibility integrity

The unified v0.9 control snapshot contains the full v0.8 state plus property-evidence and property-gate state, all under one outer content digest.

Restore verifies:

- outer control digest;
- frozen v0.8 base-state identity;
- canonical evidence sharing between base control and property subsystem;
- obligation, witness and attestation lineage;
- oracle provenance;
- property closure witness digests;
- property manifest/gate/terminal receipt lineage;
- dispatch/acknowledgement/effect lineage inherited from v0.8.

The frozen `_software_engineering_control_v08` implementation preserves the historical v0.8 schema. Upgrading old v0.8 state is explicit: restore it with the frozen implementation, then construct v0.9 property state rather than silently inventing property observations that never existed.

## Non-claims

F v1.0 does not claim that:

- passing tests prove unspecified behavior;
- screenshots prove interaction;
- reproduced failures prove root cause;
- benchmark numbers prove improvement without a baseline;
- multiple copied witnesses are independent evidence;
- historical green receipts remain valid after premise revocation;
- property verification grants mutation/release/deployment authority;
- external executors provide distributed exactly-once semantics.

## Validation gates

F v1.0 acceptance requires the current PR synthetic merge-ref to pass, after the latest independent subsystem merges:

- `Coding AGI Coding Organization Part V` on Python 3.11 and 3.13;
- `Nolane-AI Refoundation Epoch 0` on Python 3.11 and 3.13.

Part V must include the property-evidence, oracle-binding, complete-set property-gate and unified-control migration/state tests. Immediately before merge, re-check exact `main`, PR head, synthetic merge-ref, changed-file scope and mergeability; if `main` advances, acceptance must be repeated on the recomposed merge-ref.