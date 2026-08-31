# CURRENT — F. Software Engineering

Date: 2026-08-31
Engineering wave: v1.2.0
Unified control API: `external.software_engineering.control` v1.1.0
Property-evidence protocol: `external.software_engineering.property_evidence` v0.2.0
Property-gate protocol: `external.software_engineering.property_gate` v0.1.0
Current-property-validity protocol: `external.software_engineering.current_property_validity` v0.1.0
Effects state protocol: `external.software_engineering.effects` v0.1.0
Effect-fencing protocol: `external.software_engineering.effect_fencing` v0.1.0
Effect-journal protocol: `external.software_engineering.effect_journal` v0.1.0
Effect-recovery protocol: `external.software_engineering.effect_recovery` v0.1.0
Effect-dispatch protocol: `external.software_engineering.effect_dispatch` v0.1.0
Recovery-frontier protocol: `external.software_engineering.recovery_frontier` v0.1.0

F v1.2 strengthens the property-evidence boundary above merged v1.1. A caller may describe a proof, but it cannot manufacture the proof context that makes the claim valid. Semantic oracles, independent-source provenance, version-bound baselines and debugging falsifiers must be grounded in immutable verifier evidence rather than accepted merely because a witness object contains a plausible label.

The public control-plane state schema remains v1.1.0 because v1.2 does not rewrite historical witness/receipt payloads. The frozen property schema remains content-addressed and backward readable; v1.2 raises the semantic acceptance and restore criteria in the public property ledger.

## Canonical authority

F still has exactly five canonical component authorities:

1. `external.coding.claims`
2. `external.coding.patches`
3. `external.coding.control`
4. `external.debugging`
5. `external.ui_ux`

`software_engineering*` modules are composition/control protocols. Property obligations are `verification_scope_only`; property witnesses are `evidence_scope_only`; property closures, property gates, property-bound terminal receipts and current-property validity receipts are `candidate_only`. None grants mutation, release, deployment, Assurance acceptance, repository write authority or capability promotion.

## Governed lifecycle

```text
patch + source claims + immutable engineering operation lineage
  -> claim-state binding
  -> precondition evidence
  -> current mutation authority
  -> durable PRE_DISPATCH
  -> external executor boundary
  -> observation-only acknowledgement
  -> acknowledgement-backed local finalization
  -> postcondition evidence
  -> legacy Coding / Debug / UI verification
  -> historical engineering closure / candidate_only
  -> requirement-authority property manifest
  -> semantic property obligations
  -> verifier-attested property oracle
  -> verifier-grounded proof context
       - source provenance / independence
       - version-bound baseline when required
       - falsifier when required
  -> property witnesses
  -> per-property closure
  -> complete-set property gate
  -> historical property-bound candidate
  -> live legacy validity replay
  -> live property-gate reassessment
  -> exact source/patch drift check
  -> CURRENT PROPERTY-BOUND CANDIDATE / candidate_only
  -> premise revocation or drift reopens eligibility
```

Historical receipts remain immutable audit facts. Stronger current rules do not rewrite old digests; they determine whether historical evidence is admissible as current proof.

## Property evidence model

### Claim classes

F distinguishes the property actually being asserted:

- build integrity;
- functional behavior;
- regression preservation;
- debugging root cause;
- UI visual fidelity;
- UI interaction;
- UI accessibility;
- security property;
- performance property.

A generic green command or test run is not itself a semantic claim.

### Proof methods and exact property oracle

Supported proof methods include compile/static analysis, unit/integration/property/metamorphic/regression tests, deterministic reproduction, causal probe/bisect, visual diff, responsive/accessibility checks, interaction E2E, security tests and performance benchmarks.

Every accepted witness must match the exact patch ref/digest and source revision, use a proof method compatible with the canonical engineering evidence kind, remain live-valid and unrevoked, measure the exact declared property, and bind a verifier-attested `oracle_ref`.

This prevents a caller from relabeling `tests-pass`, `screenshot-exists` or another proxy as proof of a desired semantic property.

## v1.2 verifier-grounded proof context

### Version-bound baseline

Regression-preservation and performance claims require a baseline. Before v1.2, a non-empty caller-supplied `baseline_revision` could satisfy that structural requirement after the oracle was valid.

v1.2 separates *declaring* a baseline from *proving that the verifier actually evaluated against it*:

- no baseline still yields `missing_version_bound_baseline`;
- a baseline carried only by the witness yields `baseline_not_attested:<witness_id>`;
- an accepted baseline must occur in immutable verifier evidence/dependency lineage for a valid baseline-bearing witness;
- at least one verifier-grounded baseline is required to discharge the baseline proof role.

Therefore `baseline_revision="git:some-old-head"` cannot manufacture regression/performance evidence by itself.

### Debugging falsifier

Root-cause closure requires reproduction plus a causal probe/bisect and a falsifier. Before v1.2, the witness role plus any non-empty `falsifier_ref` could satisfy the falsifier role once the rest of the witness was valid.

v1.2 requires the exact falsifier reference to be grounded by the verifier attestation. A caller-only falsifier yields `falsifier_not_attested:<witness_id>`. At least one verifier-grounded FALSIFIER witness is necessary to discharge the root-cause falsification requirement.

This distinguishes “I wrote a plausible counterfactual label” from “the verifier actually ran or bound that discriminating probe.”

### Source-family independence

Where multiple independent sources are required, raw witness count and caller-chosen family labels do not manufacture independence. The public property ledger requires the source-family separation to be verifier-grounded, either explicitly in immutable evidence or through non-shared verifier/environment provenance according to the existing F independence policy.

### Restore semantics

Historical content-addressed state is not automatically semantically current. Public restore validates ready property closures against the stronger verifier-grounding rules.

A frozen historical receipt that was structurally valid under the older baseline/falsifier interpretation is rejected as a current ready property closure when its required proof context is absent from immutable verifier evidence. This is a monotonic truth-maintenance rule: history is not deleted, but a former acceptance cannot be laundered into present proof merely by preserving or recomputing receipt digests.

## Claim-specific proof floors

- build integrity: compile evidence;
- functional behavior: behavioral test family bound to the exact property oracle;
- regression preservation: regression evidence + verifier-grounded version baseline;
- debugging root cause: deterministic reproduction + causal probe/bisect + verifier-grounded falsifier;
- UI visual fidelity: visual-diff evidence;
- UI interaction: interaction E2E evidence; screenshots cannot substitute;
- UI accessibility: accessibility evidence;
- security: security evidence + adversarial witness semantics;
- performance: benchmark + verifier-grounded version baseline.

## Complete-set property gate

An individual ready property closure is insufficient. The property gate consumes the immutable required-property manifest supplied by requirement/goal authority and checks the complete exact set for one patch digest and source revision.

It fails closed on missing/unexpected properties, duplicates, obligation/closure digest mismatch, patch/source mismatch, revoked attestations, stale witnesses, insufficient grounded independence, ungrounded required proof context and lineage tampering. Historical witness sets are re-assessed against live evidence before current terminal eligibility can close.

## v1.1 current-validity retained

`SoftwareEngineeringCurrentPropertyValidity` remains above the immutable legacy closure and historical property gate. A current property-bound candidate requires simultaneously:

1. a current-valid legacy engineering truth view;
2. a complete semantic-property gate that re-closes against live evidence;
3. consistent legacy/property patch and source lineage;
4. an unchanged current patch identity/state digest;
5. zero live blockers.

Revocation or drift creates a newly blocked current receipt without erasing the historical green receipt.

Restore also retains the v1.1 cross-layer anti-laundering replay: canonical transaction/evidence/claim-binding truth is independently reconstructed so an attacker cannot forge both a nested legacy-validity receipt and its enclosing current-property receipt and then escape by recomputing digests.

## Coding / Debugging / UI implications

### Coding claims and patches

v1.2 does not redefine Coding Claims or Coding Patches ownership. Property state remains verification/control state and cannot authorize mutation.

### Debugging

Reproduction proves reproducibility, not cause. Root-cause closure requires a discriminating causal probe/bisect and a verifier-grounded falsifier. Revocation later reopens current eligibility without deleting the historical debugging record.

### UI/UX

UI/UX here means engineering verification/control for UI code, not a separate product frontend. Visual fidelity, accessibility and interaction remain different properties. A screenshot cannot prove click, keyboard, focus, routing or state-transition behavior; interaction claims require actual interaction E2E evidence.

## Durable dispatch frontier retained

All prior crash-consistency invariants remain in force:

- durable `PRE_DISPATCH` is `coordination_only`;
- dispatch without acknowledgement produces `EXTERNAL_STATUS_REQUIRED` and forbids automatic redispatch;
- F never invents an acknowledgement to escape uncertainty;
- application/rollback acknowledgements are `observation_only`;
- acknowledged application may recover through local finalization without reinvoking the executor;
- rollback requires independently verified restored state;
- compatibility backfill is failure-atomic;
- exactly-once claims remain limited to local finalization per immutable acknowledged lineage, not distributed exactly-once execution.

## Compatibility chain

- v0.8 snapshot -> frozen v0.8 restore -> v0.9 property lift -> v1.1 current-validity lift;
- v0.9 snapshot -> frozen v1.0 public boundary -> v1.1 current-validity lift;
- v1.1/v1.2 public state -> exact frozen-base reconstruction + current semantic replay.

v1.2 changes no historical witness or closure digest schema. It strengthens whether a ready historical property closure is admissible under the public verifier-grounding policy.

## Non-claims

F v1.2 does not claim that:

- passing tests prove unspecified behavior;
- screenshots prove interaction;
- reproduced failures prove root cause;
- a caller-declared baseline proves a comparison happened;
- a caller-declared falsifier proves a discriminating probe happened;
- copied or renamed witnesses are independent evidence;
- historical green receipts remain current after premise revocation;
- content-digest consistency alone proves semantic truth;
- property verification grants mutation/release/deployment authority;
- external executors provide distributed exactly-once semantics.

## Validation gates

F v1.2 final acceptance requires the exact latest PR synthetic merge-ref to pass, after all concurrent subsystem movement:

- `Coding AGI Coding Organization Part V` on Python 3.11 and 3.13;
- `Nolane-AI Refoundation Epoch 0` on Python 3.11 and 3.13.

Part V must include oracle binding, source-family independence, verifier-grounded baseline/falsifier tests, frozen-state restore regression, complete-set property gating, live reopening and v1.1 cross-layer anti-laundering regressions.

Immediately before merge, re-check exact `main`, PR head, synthetic merge-ref, changed-file scope and mergeability. If `main` or head moves, acceptance becomes stale and must be repeated on the exact recomposed edge.
