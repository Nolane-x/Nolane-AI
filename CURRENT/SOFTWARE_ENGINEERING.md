# CURRENT — F. Software Engineering

Date: 2026-09-02
Engineering wave: v1.4.0
Unified control API: `external.software_engineering.control` v1.1.0
Canonical Coding Claims: `external.coding.claims` v0.0.2
Canonical Coding Patches: `external.coding.patches` v0.0.2
Property-evidence protocol: `external.software_engineering.property_evidence` v0.3.0
Property-gate protocol: `external.software_engineering.property_gate` v0.1.0
Current-property-validity protocol: `external.software_engineering.current_property_validity` v0.1.0
Effects state protocol: `external.software_engineering.effects` v0.1.0
Effect-fencing protocol: `external.software_engineering.effect_fencing` v0.1.0
Effect-journal protocol: `external.software_engineering.effect_journal` v0.1.0
Effect-recovery protocol: `external.software_engineering.effect_recovery` v0.1.0
Effect-dispatch protocol: `external.software_engineering.effect_dispatch` v0.1.0
Recovery-frontier protocol: `external.software_engineering.recovery_frontier` v0.1.0

F v1.4 keeps the v1.3 provenance-aware Coding Patches authority, v1.2 epoch-fenced Coding Claims authority and v1.1 truth-maintained engineering candidate plane intact, then closes semantic proof laundering in the public property-evidence protocol. A caller can no longer turn a coarse canonical `TEST` or `ROOT_CAUSE` attestation into a stronger property proof merely by choosing `proof_method`, `baseline_revision`, `falsifier_ref`, witness role or `adversarial=True` metadata.

The frozen v0.2 witness schema is not changed. Instead, public property evidence advances to v0.3.0 and requires policy-significant semantic claims to be grounded in immutable verifier evidence. Exact markers such as `proof-method:<method>`, `baseline-revision:<revision>`, `falsifier-ref:<ref>`, `witness-role:<role>` and `adversarial:true` are verifier-owned facts; production never synthesizes them on behalf of a caller.

The strongest positive result remains deliberately narrow. Property witnesses remain `evidence_scope_only`, and property closures/property gates/current-property receipts remain `candidate_only`. F v1.4 does not gain repository mutation, merge, release, deployment, Assurance-acceptance or capability-promotion authority. Historical v0.2 state remains audit-compatible, but historical `ready=True` is not imported as current semantic authority when its policy-significant semantics are not verifier-grounded.

The public Software Engineering control plane remains v1.1.0 because v1.4 does not reinterpret its frozen outer state schema or widen its authority. The five canonical F component revisions also remain unchanged: the change is a composition/control protocol hardening, not a transfer of canonical component ownership.

## Canonical authority

F has exactly five canonical component authorities:

1. `external.coding.claims`
2. `external.coding.patches`
3. `external.coding.control`
4. `external.debugging`
5. `external.ui_ux`

`software_engineering*` modules remain composition/control protocols. Property obligations are `verification_scope_only`; property witnesses are `evidence_scope_only`; property closures, property gates, property-bound terminal receipts and current-property validity receipts are `candidate_only`.

Claim leases and claim-handoff receipts are `coordination_only`. Patch transition receipts are fixed to `patch_transition_only`. Neither category grants repository mutation, merge, release or deployment authority.

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
  -> register patch
     -> legacy v0.0.1-compatible unbound patch, or
     -> exact artifact digest + base source revision + immutable operation_ref
     -> content-addressed PatchProvenanceEnvelope
     -> idempotent exact-intent registration / operation-ref rebinding rejection
     -> content-addressed transition genesis
  -> canonical compile + test attestations for exact artifact digest/source revision
  -> verify_patch()
     -> content-addressed VERIFIED transition receipt
     -> authority = patch_transition_only
  -> live evidence revalidation + optional current artifact/source drift check
     -> CURRENTLY VERIFIED or reopened
  -> engineering operation_ref
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
  -> verifier-attested semantic proof markers
  -> exact property witnesses
  -> per-property closure
  -> complete-set property gate / historical candidate_only fact
  -> legacy-closure + property-gate terminal binding
  -> PROPERTY-BOUND CANDIDATE / historical candidate_only fact
  -> live legacy validity replay
  -> live property-gate reassessment
  -> exact source/patch drift check
  -> CURRENT PROPERTY-BOUND CANDIDATE / candidate_only
  -> premise revocation, source drift or semantic-proof invalidation reopens eligibility
```

The architecture remains monotonic. Historical claim, patch transition, Coding, Debug, UI/UX, engineering closure and property-gate receipts remain audit facts. Current views are re-evaluated rather than rewriting historical green state.

## v1.2 Coding Claims — epoch-fenced ownership retained

### Exclusive collision semantics

An `EXCLUSIVE_WRITE` claim conflicts with any overlapping active exclusive claim outside the exact same `(agent_id, task_id)` owner context. Reusing the same agent identity for a different task does not bypass exclusivity. File, symbol and directory-prefix overlap are covered by the canonical conflict check.

### Bound claim leases

A currentness-aware claim may be acquired with both `source_revision` and immutable `operation_ref`. The fields are all-or-nothing. A bound acquisition produces a `CodeClaimLease` containing exact claim identity, operation ref, source revision, positive monotonic epoch, canonical claim-intent digest, `coordination_only` authority, content digest and content-addressed lease id.

Retrying the same operation ref with the same exact intent returns the existing claim. Reusing it for a different claim intent fails closed.

### Current coverage

Legacy `covers(...)` remains available for historical unbound state. Mutation-sensitive callers use epoch/revision-aware current coverage. `covers_current(...)` requires matching agent, task, source revision, minimum epoch and requested source scope. Historical active-looking ownership therefore cannot prove current ownership after revision or epoch drift.

### Atomic claim handoff

Ownership transfer is a first-class atomic supersession operation. A valid handoff requires an active old claim, bound old lease, authorized actor, exact expected epoch, fresh target source revision and immutable handoff operation ref. The new claim preserves exact files, symbols, directory prefixes and claim mode. The new lease receives a strictly newer epoch. The content-addressed handoff receipt binds both old and new claim/lease lineages and remains `coordination_only`.

A retry with the same handoff operation ref and exact intent is idempotent. Rebinding that operation ref to another intent or using a stale epoch fails before mutation.

## v1.3 Coding Patches — provenance and verified-transition authority retained

### Patch provenance envelope

A provenance-aware registration supplies all three of:

- `patch_artifact_digest` — immutable digest of the patch artifact;
- `base_source_revision` — exact source revision against which that artifact was produced;
- `operation_ref` — immutable idempotency identity for patch registration.

Supplying only a subset is rejected. The canonical `PatchProvenanceEnvelope` additionally binds producer, task, work id, plan/architecture versions, normalized touched file/symbol scope, artifact id, declared compile/test/static references, known risks and plan/architecture concern references. The content digest therefore represents the exact registration intent, not merely the artifact name.

The provenance id is content-addressed. Retrying the same `operation_ref` with the same exact provenance returns the already registered patch. Reusing that operation ref for a changed artifact digest, source revision, scope, evidence declaration or other registration intent fails closed.

Legacy v0.0.1 registration remains available when none of the three provenance fields is supplied. Compatibility state is intentionally unbound and cannot later masquerade as provenance-aware current verification.

### Transition receipts

Every provenance-aware patch receives a content-addressed transition genesis. Subsequent provenance-aware status changes append `PatchTransitionReceipt` records containing:

- exact patch id;
- provenance id and provenance digest;
- positive contiguous per-patch sequence;
- exact predecessor receipt id/digest;
- exact from/to status;
- canonical evidence attestation ids/digests when required;
- fixed authority `patch_transition_only`;
- content digest and content-addressed receipt id.

A transition receipt proves a historical Coding Patches transition only. It cannot authorize mutation, merge, release, deployment, Assurance acceptance or capability promotion.

### VERIFIED cannot be label-laundered

Direct `set_status(..., VERIFIED)` is forbidden. `VERIFIED` is reachable only through `verify_patch(...)` with a configured canonical `EngineeringEvidenceLedger`.

`CodingControlPlane.assess_readiness(...)` is an observational/control receipt, not a patch-transition authority. A clean readiness result does not mutate the patch status to `VERIFIED`; a failed readiness result does not terminalize the patch. Readiness and canonical patch verification therefore remain separate evidence/control lines.

`REJECTED` and `SUPERSEDED` are terminal patch states. Once either state is recorded, neither `set_status(...)` nor `verify_patch(...)` may resurrect that patch into another state. A new attempt must mint a new patch/provenance lineage instead of rewriting terminal history.

Verification requires at minimum both canonical `COMPILE` and `TEST` attestations. Every referenced attestation must simultaneously be:

1. passed and live in the canonical evidence ledger;
2. produced under the engineering verifier constraints already enforced by that ledger;
3. bound to the exact `patch_artifact_id`;
4. bound to the exact `patch_artifact_digest`;
5. bound to the exact `base_source_revision`.

The resulting receipt stores exact attestation ids and digests. Caller-provided strings such as historical `compile_evidence_refs` and `test_evidence_refs` can make a patch `EVIDENCE_READY` for compatibility, but cannot manufacture `VERIFIED` authority.

### Historical verification versus current verification

A successful verification transition is immutable history. It does not remain eternally current.

`is_currently_verified(...)` revalidates the latest VERIFIED receipt against the live canonical evidence ledger. Revoking any required attestation reopens current verification while leaving the historical patch and transition receipt unchanged. The caller may additionally supply the current artifact digest and source revision; either mismatch fails closed.

This distinction is intentional:

- historical `patch.status == VERIFIED` records what was concluded at that transition;
- current verification answers whether the latest evidence lineage remains live for the exact bound artifact/source state.

## v1.3 restore and anti-laundering invariants retained

v1.3 restore does not trust serialized provenance or transition metadata merely because an attacker recomputed an outer digest.

It verifies:

- supported snapshot version;
- canonical provenance digest/id reproduction;
- one immutable operation ref -> one exact provenance binding;
- one provenance envelope -> one canonical patch owner;
- exact candidate/provenance field equality;
- transition digest/id integrity;
- canonical unique evidence-id ordering;
- VERIFIED transitions contain evidence references;
- exact transition provenance id/digest lineage;
- globally unique transition receipt ids;
- contiguous per-patch transition sequence;
- exact predecessor receipt id/digest and from-status lineage;
- candidate status equals the transition frontier;
- provenance-aware patches always have transition history;
- provenance-aware VERIFIED patches terminate in a VERIFIED evidence-bearing transition;
- when the canonical evidence ledger is available at restore, exact live evidence identity/digest and provenance binding are replayed;
- v0.0.2 `patch_counter` equals the recorded patch-id frontier exactly.

The exact counter rule prevents both rollback and frontier inflation. A v0.0.2 snapshot cannot raise the serialized patch counter above actual recorded patch history and thereby manufacture future id space.

A recomputed VERIFIED transition without canonical evidence is rejected. Content-addressing protects integrity; it is not treated as semantic truth by itself.

Legacy v0.0.1 snapshots remain restorable without invented provenance envelopes, transition receipts, artifact digests, source revisions, operation refs or current verification authority. A historical legacy `VERIFIED` label remains an audit-compatible legacy fact only; `is_currently_verified(...)` returns false because no v0.0.2 evidence/provenance lineage exists.

## v1.4 Property Evidence — semantic verifier grounding

F v1.4 moves semantic authority from caller-owned witness labels to immutable verifier attestations while preserving the frozen witness record shape.

### Proof-method grounding

Canonical evidence kinds are intentionally coarser than some property proof methods. `TEST` can back unit, integration, property, metamorphic or regression testing, and `ROOT_CAUSE` can back causal-probe or bisect evidence. Therefore kind matching alone cannot authorize those semantic distinctions.

For ambiguous method families, the verifier must bind the exact marker `proof-method:<method>`. If an attestation advertises any `proof-method:*` marker, a caller also cannot reinterpret it as a different method. Exact marker mismatch fails before witness admission.

Methods whose canonical evidence kind is already semantically singular remain kind-grounded unless an attestation explicitly declares a conflicting proof-method marker; an explicit marker never becomes advisory metadata.

### Baseline, falsifier and role grounding

Policy-significant witness fields require exact immutable evidence refs:

- `baseline_revision=<revision>` requires `baseline-revision:<revision>`;
- `falsifier_ref=<ref>` requires `falsifier-ref:<ref>`;
- any non-`direct` role requires `witness-role:<role>`;
- `adversarial=True` requires `adversarial:true`.

These markers are not inferred from the caller, method kind, claim class or a previously green closure. The verifier must have emitted them in the canonical attestation. Legitimate tests and integrations therefore create a new canonical verifier attestation carrying the exact semantic markers rather than asking production to decorate evidence after the fact.

### Assessment and independence composition

Semantic grounding is checked both at witness admission and during live property assessment. The v1.3 source-family independence calculation only treats a witness as baseline-valid after its semantic authority remains grounded. This prevents an ungrounded semantic witness from participating indirectly in an independence proof.

If the frozen v0.2 assessment would transiently create an optimistic green receipt but the v0.3 semantic layer immediately invalidates that result, the new optimistic receipt is not retained as history. Pre-existing historical receipts are never deleted or rewritten.

### v0.2 audit compatibility and v0.3 restore

The frozen v0.2 parser remains the authority for the historical witness/state shape. Public v0.3 restore accepts both v0.2 and v0.3 outer property-evidence protocol versions, normalizes only the outer tag for the frozen parser, and never rewrites witness content or fabricates verifier markers.

A restored v0.2 ledger preserves its historical serialization version until new public v0.3 work is performed. This allows containing historical control snapshots to remain state-identical when merely audited. Once a new witness or assessment is produced, the public property ledger serializes as v0.3.0.

Compatibility is not semantic promotion. Any historical `ready=True` property receipt whose policy-significant semantics are not verifier-grounded fails closed during public restore/current replay. A native v0.3 snapshot is stricter still: it cannot contain a witness that could not have passed the v0.3 admission boundary.

## Property evidence model retained from v1.0/v1.1

The property ledger distinguishes build integrity, functional behavior, regression preservation, debugging root cause, UI visual fidelity, UI interaction, UI accessibility, security property and performance property.

Supported proof methods include compile/static analysis, unit/integration/property/metamorphic/regression tests, deterministic reproduction, causal probe/bisect, visual diff, responsive/accessibility checks, interaction E2E, security tests and performance benchmarks. A witness binds the exact property and verifier-attested oracle; passing a generic command is not sufficient evidence for an arbitrary semantic claim.

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

It fails closed on missing or unexpected properties, duplicates, obligation/closure digest mismatch, patch/source mismatch, revoked attestations, stale witnesses, ungrounded semantic metadata, insufficient source-family independence and lineage tampering. Each assessment re-runs the historical witness set against the live evidence ledger.

`SoftwareEngineeringCurrentPropertyValidity` remains above the immutable legacy closure and historical property gate. Current eligibility requires simultaneous live validity of the legacy engineering truth line, complete semantic-property gate, exact historical lineage, current patch identity/state digest and absence of live blockers.

Historical green receipts remain audit facts. Premise revocation or semantic-proof invalidation creates a newly blocked current view rather than deleting or rewriting history.

## Coding / Debugging / UI implications

### Coding claims

Claim leases prove coordination facts about current source ownership only when exact revision/epoch conditions remain satisfied. They are not repository mutation authority.

### Coding patches

v1.3 makes patch provenance and verification lineage explicit. An opaque artifact id or mutable `VERIFIED` label no longer suffices for provenance-aware current verification. Patch verification remains separate from claim ownership, patch application, merge, release and deployment decisions.

### Debugging

A root-cause statement cannot close from reproduction alone. It requires a discriminating causal probe/bisect and a falsifier. F v1.4 additionally requires the verifier to attest the exact causal method, non-direct falsifier role and falsifier reference used as semantic authority. If supporting evidence is later revoked or semantic grounding fails, current eligibility reopens without erasing valid historical audit facts.

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

The unified Software Engineering v1.1 snapshot retains its frozen v1.0/v0.9 property state and current-property-validity substate under one outer content digest. F v1.4 hardens the current public property-evidence protocol independently and does not reinterpret historical Software Engineering control-plane receipts, v1.2 claim leases/handoffs or v1.3 Coding Patches transitions.

Compatibility remains explicit:

- Software Engineering v0.8 snapshot -> frozen v0.8 restore -> v0.9 property lift -> v1.1 current-validity lift;
- Software Engineering v0.9 snapshot -> frozen v1.0 public boundary -> v1.1 current-validity lift;
- Software Engineering v1.1 snapshot -> exact frozen-base reconstruction + current-validity semantic replay;
- Property Evidence v0.2 snapshot -> frozen v0.2 shape verification -> public v0.3 semantic replay without invented markers;
- Property Evidence v0.3 snapshot -> exact frozen-shape verification + mandatory semantic-grounding validation;
- Coding Claims legacy unbound snapshot -> canonical v0.0.2 restore without invented lease/epoch state;
- Coding Claims v0.0.2 bound snapshot -> exact lease/handoff lineage replay and exact epoch-frontier validation;
- Coding Patches v0.0.1 snapshot -> compatibility restore without invented provenance/transition/current-verification authority;
- Coding Patches v0.0.2 snapshot -> exact provenance + transition lineage replay and exact patch-counter frontier validation.

The v0.0.1 positional constructor order of `CodingPatchCandidate` is preserved through its historical `status` field. v1.3 provenance fields are appended after that ABI boundary rather than inserted into older positional slots.

## Non-claims

F v1.4 does not claim that:

- witness metadata can manufacture a stronger proof method than the verifier attested;
- a baseline revision is authoritative without an exact verifier-owned baseline marker;
- a falsifier role/reference is authoritative because a caller labeled it as such;
- `adversarial=True` is semantic evidence without `adversarial:true` in immutable verifier evidence;
- historical v0.2 `ready=True` automatically becomes current v0.3 semantic authority;
- property protocol v0.3 expands canonical component ownership or write authority;
- a patch `VERIFIED` label grants repository mutation, merge, release or deployment authority;
- historical legacy VERIFIED state proves current v1.3 verification;
- content-addressed provenance or transition receipts alone prove semantic truth;
- caller-supplied compile/test strings can manufacture canonical verification;
- a historical VERIFIED transition remains current after evidence revocation or artifact/source drift;
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
- property verification grants mutation/release/deployment authority;
- external executors provide distributed exactly-once semantics.

## Validation gates

F v1.4 final acceptance requires the exact latest PR synthetic merge-ref, after the latest independent subsystem merges, to pass:

- `Coding AGI Coding Organization Part V` on Python 3.11 and 3.13;
- `Nolane-AI Refoundation Epoch 0` on Python 3.11 and 3.13.

Part V must cover at minimum:

- generic TEST -> stronger property-test relabeling rejection;
- mismatched verifier proof-method marker rejection;
- verifier-grounded baseline revision requirement;
- verifier-grounded falsifier role and reference requirement;
- caller-manufactured adversarial semantics rejection;
- exact semantic markers supporting legitimate property closure;
- v0.2 historical ready semantic laundering rejection on public restore;
- source-family independence grounding retained from v1.3 property hardening;
- direct VERIFIED status-label laundering rejection;
- content-bound provenance registration;
- exact operation-ref idempotency and changed-intent rebinding rejection;
- canonical compile + test evidence requirement;
- exact artifact digest/source revision evidence binding;
- historical VERIFIED transition receipt with `patch_transition_only` authority;
- current verification reopening after evidence revocation;
- current verification reopening after artifact/source drift;
- candidate/provenance restore binding;
- recomputed VERIFIED receipt without evidence rejection;
- operation-ref/provenance tamper rejection;
- transition frontier replay;
- v0.0.2 patch-counter frontier inflation rejection;
- v0.0.1 positional constructor compatibility;
- legacy v0.0.1 snapshot restore without invented current verification authority;
- all retained v1.2 Coding Claims regressions and earlier organization tests.

Refoundation must independently verify canonical native ownership, unchanged F canonical component revisions, component-version metadata, historical bridge identity, repository audit/materialization freshness, Truth/Knowledge contracts, organization/campaign/execution regressions and frozen Neural R2.3 metadata on both supported Python versions.

Immediately before merge, re-check exact `main`, PR head, synthetic merge-ref, changed-file scope and mergeability. If `main` advances, acceptance is stale and must be repeated on the recomposed edge.
