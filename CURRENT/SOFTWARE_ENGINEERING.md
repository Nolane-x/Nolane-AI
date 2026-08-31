# CURRENT — F. Software Engineering

Date: 2026-08-31
Engineering wave: v1.1.0
Unified control API: `external.software_engineering.control` v1.1.0
Property-evidence protocol: `external.software_engineering.property_evidence` v0.1.0
Property-gate protocol: `external.software_engineering.property_gate` v0.1.0
Current-property-validity protocol: `external.software_engineering.current_property_validity` v0.1.0
Effects state protocol: `external.software_engineering.effects` v0.1.0
Effect-fencing protocol: `external.software_engineering.effect_fencing` v0.1.0
Effect-journal protocol: `external.software_engineering.effect_journal` v0.1.0
Effect-recovery protocol: `external.software_engineering.effect_recovery` v0.1.0
Effect-dispatch protocol: `external.software_engineering.effect_dispatch` v0.1.0
Recovery-frontier protocol: `external.software_engineering.recovery_frontier` v0.1.0

F v1.1 turns F v1.0 property evidence into a live truth-maintained engineering candidate protocol. A historical green engineering closure and a historical green property gate are immutable audit facts, not perpetual authorization. Current candidate eligibility is a separate content-addressed view that rechecks the legacy engineering truth line and the semantic-property truth line against canonical live evidence, source revision and patch state.

The public control plane advances to v1.1.0. The F v1.0 public boundary is frozen in `_software_engineering_control_v10.py`, while `_software_engineering_control_v09.py` and `_software_engineering_control_v08.py` continue to preserve their historical state semantics. Old v0.8/v0.9 snapshots are lifted explicitly; their historical receipts are not reinterpreted under v1.1.

## Canonical authority

F still has exactly five canonical component authorities:

1. `external.coding.claims`
2. `external.coding.patches`
3. `external.coding.control`
4. `external.debugging`
5. `external.ui_ux`

`software_engineering*` modules remain composition/control protocols. Property obligations are `verification_scope_only`; property witnesses are `evidence_scope_only`; property closures, property gates, property-bound terminal receipts and current-property validity receipts are `candidate_only`. None grants mutation, release, deployment, Assurance acceptance, repository write authority or capability promotion.

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
  -> legacy engineering closure / historical candidate_only fact
  -> externally supplied required-property manifest
  -> claim-class-specific property obligations
  -> verifier-attested property oracles
  -> exact property witnesses
  -> per-property closure
  -> complete-set property gate / historical candidate_only fact
  -> legacy-closure + property-gate terminal binding
  -> PROPERTY-BOUND CANDIDATE / historical candidate_only fact
  -> live legacy validity replay
  -> live property-gate reassessment
  -> exact source/patch drift check
  -> CURRENT PROPERTY-BOUND CANDIDATE / candidate_only
  -> premise revocation or drift reopens current eligibility
```

The architecture is monotonic: historical Coding, Debug, UI/UX, engineering closure and property-gate receipts remain immutable. v1.1 adds a new current-truth projection instead of mutating old payloads or retroactively changing their digests.

## Property evidence model

### Claim classes

The property ledger distinguishes the semantic claim being made:

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

### Proof methods and oracle binding

Supported proof methods include compile/static analysis, unit/integration/property/metamorphic/regression tests, deterministic reproduction, causal probe/bisect, visual diff, responsive/accessibility checks, interaction E2E, security tests and performance benchmarks.

A witness must bind the exact property and a verifier-attested `oracle_ref`. The oracle must occur in immutable verifier evidence/dependency lineage, the attestation must match the exact patch digest and source revision, the attestation must remain live-valid, and proof method must agree with the canonical evidence kind. This blocks relabeling an unrelated green test as proof of a desired semantic property.

### Claim-specific proof floors

- build integrity requires compile evidence;
- functional behavior requires a behavioral test family bound to the exact property oracle;
- regression preservation requires regression evidence plus a version-bound baseline;
- debugging root cause requires deterministic reproduction, causal probe/bisect and a falsifier;
- UI visual fidelity requires visual-diff evidence;
- UI interaction requires interaction E2E evidence; screenshots cannot substitute;
- UI accessibility requires accessibility evidence;
- security requires security evidence plus adversarial witness semantics;
- performance requires a benchmark plus a version-bound baseline.

Where multiple independent sources are required, independence is counted by verifier-attested source family rather than raw witness count.

## Complete-set property gate

A ready individual property closure is insufficient. The property gate consumes the immutable required-property manifest supplied by the requirement/goal authority and checks the complete exact set for one patch digest and source revision.

It fails closed on missing or unexpected properties, duplicates, obligation/closure digest mismatch, patch/source mismatch, revoked attestations, stale witnesses, insufficient source-family independence, and lineage tampering. Each assessment re-runs the historical witness set against the live evidence ledger.

The terminal property-bound receipt remains a historical `candidate_only` result. It is intentionally not interpreted as proof that its premises are still true later.

## v1.1 current-validity truth maintenance

`SoftwareEngineeringCurrentPropertyValidity` sits above the immutable legacy closure and historical property gate. It emits `EngineeringCurrentPropertyBoundReceipt`, binding:

- canonical base engineering closure id/digest;
- canonical historical property gate id/digest;
- canonical property manifest id/digest;
- the newly evaluated legacy `EngineeringCurrentValidityReceipt` id/digest;
- the newly re-assessed live property gate id/digest;
- exact patch ref/digest;
- the source revision being evaluated;
- deterministic current/blocking reasons;
- authority fixed to `candidate_only`.

A current result requires all of the following simultaneously:

1. the legacy engineering closure still has a current-valid legacy truth view;
2. the complete semantic-property gate re-closes against live evidence;
3. historical legacy/property lineages still identify the same patch digest and source revision;
4. the supplied current patch object still has the same identity and state digest;
5. no live blocker remains.

Revocation does not delete or mutate prior green receipts. It causes a newly assessed current receipt to become blocked. This preserves auditability while preventing historical success from masquerading as present truth.

### Cross-layer anti-laundering restore

Content digests alone are not considered sufficient restore proof. An attacker able to edit serialized state could otherwise modify both a nested legacy-validity receipt and its enclosing current-property receipt, recompute both digests, and make the two forged objects appear mutually consistent.

v1.1 therefore performs semantic replay during restore. It independently reconstructs all legacy blockers available from canonical state, including:

- base-closure readiness;
- transaction patch/source lineage;
- candidate-ready transaction phase and closure binding;
- source-revision freshness;
- current validity of every canonical legacy attestation;
- canonical claim-binding presence and identity.

The property side is independently recomputed through a fresh complete-set property-gate assessment. If a nested validity receipt omits a blocker that canonical live evidence reproduces, restore rejects the snapshot even when every attacker-controlled digest was recomputed correctly.

Patch-object drift that depends on an external current patch object is checked on every live `assess(...)` call. Persisted receipts remain historical observations; downstream code must request a fresh assessment for present eligibility rather than treating a restored `current=True` row as eternal authority.

## Coding / Debugging / UI implications

### Coding claims and patches

v1.1 does not redefine Coding Claims or Coding Patches ownership. Mutation remains governed by canonical Coding/F mechanisms. Current-property state is verification/control state only and cannot authorize a write.

### Debugging

A root-cause statement cannot close from reproduction alone. It requires a discriminating causal probe/bisect and a falsifier. If the supporting evidence is later revoked, current eligibility reopens without erasing the historical debugging result.

### UI/UX

UI/UX here means engineering verification/control for UI code, not a separate product frontend. Visual fidelity, accessibility and interaction remain separate properties. A screenshot does not prove click, keyboard, focus, routing or state-transition behavior; interaction-sensitive claims require actual interaction E2E evidence.

## Durable dispatch frontier retained

All crash-consistency invariants remain in force:

- `PRE_DISPATCH` is durable and `coordination_only`;
- dispatch without acknowledgement yields `EXTERNAL_STATUS_REQUIRED` and forbids automatic redispatch;
- F never invents an acknowledgement to escape uncertainty;
- application/rollback acknowledgements are `observation_only`;
- acknowledged application can recover by local finalization without re-invoking the executor;
- rollback requires independently verified restored state;
- compatibility backfill is failure-atomic;
- exactly-once claims remain limited to local finalization per immutable acknowledged lineage, not distributed exactly-once execution.

## State and compatibility integrity

The unified v1.1 control snapshot contains the frozen v1.0/v0.9 property state plus the new current-property-validity substate under one outer content digest.

Restore verifies outer digest, frozen historical state identity, shared canonical evidence, property evidence/gate lineage, current-property nested component identity/version, live property re-evaluation, canonical legacy truth replay, and the inherited dispatch/effect lineage. Recomputing an outer digest cannot bypass nested semantic validation.

Compatibility is explicit:

- v0.8 snapshot -> frozen v0.8 restore -> v0.9 property lift -> v1.1 current-validity lift;
- v0.9 snapshot -> frozen v1.0 public boundary -> v1.1 current-validity lift;
- v1.1 snapshot -> exact frozen-base reconstruction + current-validity semantic replay.

No migration invents property witnesses or current-validity observations that did not exist historically.

## Non-claims

F v1.1 does not claim that:

- passing tests prove unspecified behavior;
- screenshots prove interaction;
- reproduced failures prove root cause;
- benchmark numbers prove improvement without a baseline;
- copied witnesses are independent evidence;
- historical green receipts remain current after premise revocation;
- a restored `current=True` receipt is perpetual proof without a fresh current assessment;
- content-digest consistency alone proves semantic truth;
- property verification grants mutation/release/deployment authority;
- external executors provide distributed exactly-once semantics.

## Validation gates

F v1.1 final acceptance requires the exact latest PR synthetic merge-ref, after the latest independent subsystem merges, to pass:

- `Coding AGI Coding Organization Part V` on Python 3.11 and 3.13;
- `Nolane-AI Refoundation Epoch 0` on Python 3.11 and 3.13.

Part V must include property evidence/oracle binding, complete-set property gating, live legacy/property reopening, public-control migration/state tests, and the cross-layer recomputed-truth laundering adversarial regression. Immediately before merge, re-check exact `main`, PR head, synthetic merge-ref, changed-file scope and mergeability. If `main` advances, acceptance is stale and must be repeated on the recomposed edge.