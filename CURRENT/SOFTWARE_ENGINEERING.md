# CURRENT — F. Software Engineering

Date: 2026-09-01
Engineering wave: v1.2.0
Unified control API: `external.software_engineering.control` v1.1.0
Canonical Coding Claims: `external.coding.claims` v0.0.2
Property-evidence protocol: `external.software_engineering.property_evidence` v0.1.0
Property-gate protocol: `external.software_engineering.property_gate` v0.1.0
Current-property-validity protocol: `external.software_engineering.current_property_validity` v0.1.0
Effects state protocol: `external.software_engineering.effects` v0.1.0
Effect-fencing protocol: `external.software_engineering.effect_fencing` v0.1.0
Effect-journal protocol: `external.software_engineering.effect_journal` v0.1.0
Effect-recovery protocol: `external.software_engineering.effect_recovery` v0.1.0
Effect-dispatch protocol: `external.software_engineering.effect_dispatch` v0.1.0
Recovery-frontier protocol: `external.software_engineering.recovery_frontier` v0.1.0

F v1.2 keeps the v1.1 truth-maintained engineering candidate plane intact and hardens the canonical Coding Claims authority beneath it. The new claim protocol makes mutable ownership currentness explicit: exclusive scope, immutable operation identity, source revision, monotonic claim epoch and atomic handoff are now distinct pieces of coordination state. Historical claim objects are not allowed to masquerade as current mutation coverage after revision or epoch drift.

The public Software Engineering control plane remains v1.1.0 because v1.2 does not reinterpret its frozen state schema or widen its authority. The canonical `external.coding.claims` component advances from v0.0.1 to v0.0.2. The historical `cogcoder.organization.code_claims` surface remains an exact public-object bridge to the canonical implementation.

## Canonical authority

F has exactly five canonical component authorities:

1. `external.coding.claims`
2. `external.coding.patches`
3. `external.coding.control`
4. `external.debugging`
5. `external.ui_ux`

`software_engineering*` modules remain composition/control protocols. Property obligations are `verification_scope_only`; property witnesses are `evidence_scope_only`; property closures, property gates, property-bound terminal receipts and current-property validity receipts are `candidate_only`.

Claim leases and claim-handoff receipts are `coordination_only`. They coordinate who may be treated as holding current source scope; they do not themselves mutate files, release code, deploy artifacts, accept Assurance claims, or promote capabilities.

## Governed lifecycle

```text
work / source scope
  -> acquire canonical code claim
     -> optional immutable source_revision + operation_ref binding
     -> content-addressed coordination-only lease
     -> monotonic claim epoch
  -> current scope coverage requires matching agent + task + source revision + minimum epoch
  -> optional atomic ownership handoff
     -> verify active old claim + authorized actor + exact old epoch
     -> preserve exact source scope and claim mode
     -> supersede old claim
     -> mint new claim + newer lease
     -> content-addressed coordination-only handoff receipt
  -> patch + engineering operation_ref
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
  -> premise revocation, source drift or ownership drift reopens eligibility
```

The architecture remains monotonic: historical Coding, Debug, UI/UX, engineering closure and property-gate receipts remain immutable. v1.2 does not mutate old claims into new claims during ownership transfer; it supersedes the old claim and emits a new claim/lease lineage.

## v1.2 Coding Claims — epoch-fenced ownership

### Exclusive collision semantics

An `EXCLUSIVE_WRITE` claim conflicts with any overlapping active exclusive claim outside the exact same `(agent_id, task_id)` owner context. Reusing the same agent identity for a different task no longer bypasses exclusivity. File, symbol and directory-prefix overlap are all covered by the canonical conflict check.

This prevents a single coding agent from silently owning overlapping exclusive scope for two independent tasks and then presenting either task as the legitimate owner of the same source region.

### Bound claim leases

A currentness-aware claim may be acquired with both:

- `source_revision` — the exact source revision to which ownership applies;
- `operation_ref` — an immutable idempotency key for that acquisition operation.

The two fields are all-or-nothing. Supplying only one is rejected.

A bound acquisition produces a `CodeClaimLease` containing:

- `claim_id`;
- immutable `operation_ref`;
- exact `source_revision`;
- positive monotonic `epoch`;
- canonical claim-intent digest;
- authority fixed to `coordination_only`;
- content digest and content-addressed lease id.

Retrying the same `operation_ref` with the same exact intent returns the existing claim without changing state. Reusing that `operation_ref` for a different claim intent fails closed.

### Current coverage

Legacy `covers(...)` remains available for compatibility with unbound historical claim state. Current mutation-sensitive callers must use the epoch/revision-aware coverage path.

`covers_current(...)` only counts active claims whose lease simultaneously matches:

1. the requested agent;
2. the requested task;
3. the exact current source revision;
4. a lease epoch at least as new as the required minimum epoch;
5. the requested file/symbol scope.

An old active-looking claim therefore cannot prove current ownership after source revision drift or after downstream logic requires a newer ownership epoch.

## Atomic claim handoff

Ownership transfer is represented as a first-class atomic supersession operation, not as an informal release followed by an unrelated new claim.

A valid handoff requires:

- an active old claim;
- an existing bound old lease;
- actor authorization by the old owner, `coding.chief`, or `nolane.central`;
- exact `expected_epoch == old_lease.epoch`;
- a fresh target source revision;
- an immutable handoff `operation_ref`.

The new claim preserves the old claim's exact files, symbols, directory prefixes and claim mode while allowing a new agent/task owner and source revision. The new lease receives an epoch strictly greater than the old lease epoch. Only after all validation and content-addressed objects are prepared does the ledger supersede the old claim and install the new claim, lease, receipt and operation bindings.

The `CodeClaimHandoffReceipt` binds both sides of the transition:

- old claim id, lease id/digest, source revision and epoch;
- new claim id, lease id/digest, source revision and epoch;
- actor identity;
- immutable operation ref and request-intent digest;
- authority fixed to `coordination_only`;
- content digest and content-addressed receipt id.

A retry with the same handoff operation ref and exact intent is idempotent. Rebinding that operation ref to another intent is rejected.

A stale epoch cannot authorize a handoff. Failure occurs before ledger mutation, preserving failure atomicity.

## Restore and anti-laundering invariants

v1.2 restore does not trust serialized coordination metadata merely because its fields are syntactically valid.

It verifies:

- canonical claim ids and claim counter history;
- no conflicting active exclusive ownership;
- unique claim lease per claim;
- unique lease epochs;
- lease -> claim intent lineage, including exact source revision;
- immutable operation-ref uniqueness;
- handoff receipt digest/id integrity;
- old/new lease ids, digests, revisions and epochs;
- old claim remains `SUPERSEDED`;
- exact source-scope/mode transfer across handoff;
- authorized handoff actor lineage;
- handoff request-intent recomputation;
- unique incoming handoff origin for each new claim.

### Epoch-counter anti-inflation rule

The ledger epoch counter is derived from recorded lease history, not an independently trusted number. For bound state, serialized `epoch_counter` must equal the maximum recorded lease epoch exactly.

A snapshot that raises `epoch_counter` above the recorded lease frontier is rejected, just as a counter behind the recorded frontier is rejected. This closes a restore laundering path where an attacker could previously inflate the counter, make future leases jump to an invented epoch and weaken the meaning of monotonic fencing.

Legacy snapshots containing no bound leases/handoffs remain restorable with their historical unbound semantics. Compatibility does not invent leases, source revisions, operation refs or epochs that did not exist historically.

## Property evidence model retained from v1.0/v1.1

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

Supported proof methods include compile/static analysis, unit/integration/property/metamorphic/regression tests, deterministic reproduction, causal probe/bisect, visual diff, responsive/accessibility checks, interaction E2E, security tests and performance benchmarks.

A witness must bind the exact property and a verifier-attested oracle. Passing a generic command is not sufficient evidence for an arbitrary semantic claim.

Claim-specific proof floors remain:

- build integrity requires compile evidence;
- functional behavior requires a behavioral test family bound to the exact property oracle;
- regression preservation requires regression evidence plus a version-bound baseline;
- debugging root cause requires deterministic reproduction, causal probe/bisect and a falsifier;
- UI visual fidelity requires visual-diff evidence;
- UI interaction requires interaction E2E evidence; screenshots cannot substitute;
- UI accessibility requires accessibility evidence;
- security requires security evidence plus adversarial witness semantics;
- performance requires a benchmark plus a version-bound baseline.

## Complete-set property gate and live validity retained

A ready individual property closure is insufficient. The property gate consumes the immutable required-property manifest supplied by the requirement/goal authority and checks the complete exact set for one patch digest and source revision.

It fails closed on missing or unexpected properties, duplicates, obligation/closure digest mismatch, patch/source mismatch, revoked attestations, stale witnesses, insufficient source-family independence and lineage tampering. Each assessment re-runs the historical witness set against the live evidence ledger.

`SoftwareEngineeringCurrentPropertyValidity` remains above the immutable legacy closure and historical property gate. Current eligibility requires simultaneous live validity of the legacy engineering truth line, complete semantic-property gate, exact historical lineage, current patch identity/state digest and absence of live blockers.

Historical green receipts remain audit facts. Premise revocation creates a newly blocked current view rather than deleting or rewriting history.

## Coding / Debugging / UI implications

### Coding claims

v1.2 strengthens Coding Claims ownership without granting claims direct repository mutation authority. A lease proves a coordination fact about current scope ownership only when revision and epoch conditions remain satisfied.

### Coding patches

Coding Patches ownership and mutation semantics are not redefined in this wave. Patch application remains governed by canonical Coding/F mutation controls and engineering effect protocols.

### Debugging

A root-cause statement cannot close from reproduction alone. It requires a discriminating causal probe/bisect and a falsifier. If supporting evidence is later revoked, current eligibility reopens without erasing the historical debugging result.

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

The unified Software Engineering v1.1 snapshot retains its frozen v1.0/v0.9 property state and current-property-validity substate under one outer content digest. F v1.2 changes Coding Claims state semantics independently and does not reinterpret historical Software Engineering control-plane receipts.

Compatibility remains explicit:

- Software Engineering v0.8 snapshot -> frozen v0.8 restore -> v0.9 property lift -> v1.1 current-validity lift;
- Software Engineering v0.9 snapshot -> frozen v1.0 public boundary -> v1.1 current-validity lift;
- Software Engineering v1.1 snapshot -> exact frozen-base reconstruction + current-validity semantic replay;
- Coding Claims legacy unbound snapshot -> canonical v0.0.2 restore without invented lease/epoch state;
- Coding Claims v0.0.2 bound snapshot -> exact lease/handoff lineage replay and exact epoch-frontier validation.

## Non-claims

F v1.2 does not claim that:

- an active historical claim automatically proves current ownership;
- a claim lease grants repository mutation/release/deployment authority;
- the same agent may bypass exclusive conflict by using a different task id;
- caller-supplied epoch numbers can advance ownership history;
- a release followed by an unrelated acquire is equivalent evidence to an atomic handoff;
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

F v1.2 final acceptance requires the exact latest PR synthetic merge-ref, after the latest independent subsystem merges, to pass:

- `Coding AGI Coding Organization Part V` on Python 3.11 and 3.13;
- `Nolane-AI Refoundation Epoch 0` on Python 3.11 and 3.13.

Part V must cover at minimum:

- same-agent cross-task exclusive collision rejection;
- bound acquisition operation-ref idempotency and rebinding rejection;
- complete revision/operation binding;
- revision/epoch-aware current coverage;
- atomic supersession/handoff with exact-scope transfer;
- stale-epoch failure atomicity;
- bound state round-trip and legacy state restore;
- restore rejection of operation-ref rebinding and conflicting ownership;
- restore rejection of epoch-counter inflation;
- component-version advancement to `external.coding.claims` v0.0.2.

Refoundation must independently verify canonical native ownership, component-version metadata, historical bridge identity, repository audit/materialization freshness, Truth/Knowledge contracts, organization/campaign/execution regressions and frozen Neural R2.3 metadata on both supported Python versions.

Immediately before merge, re-check exact `main`, PR head, synthetic merge-ref, changed-file scope and mergeability. If `main` advances, acceptance is stale and must be repeated on the recomposed edge.