# Goal/Design Decision Context Pins Design

## Status

Implementation authority for the next D. Goal / Design hardening wave. This design adds a proof-carrying context artifact for already-authorized decisions. It does not replace the generic organization/memory `ContextCompiler`, Family-A truth authority, or historical Goal/Design decision receipt identity.

## Problem

The current Goal/Design stack has strong decision, terminal-integrity, truth, reopening, and stress authorities, but context is still weaker than the authority graph it is supposed to carry. The generic `ContextCompiler` assembles memories, event deltas, artifact versions, tools, identity, and authority boundaries. It does not produce an exact semantic decision context that pins terminal intent, hard constraints, anti-goals, selected champion, explicit rivals, open proof obligations, critical unknowns, contradictions, and their provenance to the exact decision authority that created them.

That gap creates a context-laundering surface: a downstream agent can receive a technically fresh context capsule while omitting a terminal constraint, forgetting a rival, carrying a stale option set, or substituting proof/uncertainty state that was not part of the admitted decision.

The Context plane therefore needs an immutable companion artifact whose semantics are re-derived from already-authorized D artifacts rather than inferred from free text.

## Architectural boundary

The new subsystem is `goal_design_context.py`, not an expansion of the generic `context.py` into a god-object.

The subsystem is an authority-preserving compiler, not a new truth source:

- terminal goal / hard constraint / non-goal / anti-goal / success criterion pins originate only from the current active `GoalIntegrityContract` bound to the decision;
- champion and rival pins originate only from the exact option set already bound by the decision receipt;
- open-proof pins originate only from the exact proof-obligation state bound by the receipt;
- critical-unknown pins originate only from the exact uncertainty state bound by the receipt and a control-plane-owned threshold;
- contradiction pins are explicit evidence-bearing assertions with a visibly weaker trust label; they can block or warn downstream reasoning but can never manufacture terminal authority;
- the compiler never invents hidden assumptions, contradictions, rivals, or decisive evidence from prose.

## Components

### 1. `DecisionContextPinKind`

Typed semantic pin kinds:

- `TERMINAL_GOAL`
- `HARD_CONSTRAINT`
- `NON_GOAL`
- `ANTI_GOAL`
- `SUCCESS_CRITERION`
- `CHAMPION`
- `RIVAL`
- `OPEN_PROOF`
- `CRITICAL_UNKNOWN`
- `CONTRADICTION`

Protected semantic kinds (`TERMINAL_GOAL`, `HARD_CONSTRAINT`, `NON_GOAL`, `ANTI_GOAL`, `SUCCESS_CRITERION`) are compiler-generated only from the active integrity contract. No caller API accepts arbitrary pins.

### 2. `DecisionContextTrust`

Every pin carries an explicit trust label:

- `INTEGRITY_AUTHORITY` — sourced from active Goal Integrity authority;
- `DECISION_AUTHORITY` — sourced from exact decision/evaluation inputs;
- `PROOF_STATE` — sourced from exact proof state bound by the decision receipt;
- `UNCERTAINTY_STATE` — sourced from exact uncertainty state bound by the decision receipt;
- `EVIDENCE_ASSERTION` — explicit contradiction evidence supplied by a caller, never promoted to protected semantic authority.

Trust labels are semantic metadata, not permissions. They make provenance visible and prevent an evidence assertion from being mistaken for terminal intent.

### 3. `DecisionContextPin`

Immutable, content-addressed pin fields:

- `goal_id`
- `kind`
- `subject_ref`
- `statement`
- `trust`
- `authority_ref`
- `authority_digest`
- canonical `provenance_refs`
- canonical `evidence_refs`
- `blocking`
- optional normalized `salience` in `[0,1]`
- derived `pin_id`

`pin_id` is the digest of all semantic fields. Pin identity cannot survive content mutation.

### 4. `DecisionContextContradiction`

Explicit contradiction evidence is represented separately so callers cannot inject arbitrary protected pins:

- `contradiction_id`
- `goal_id`
- `statement`
- canonical `subject_refs`
- non-empty `evidence_refs`
- `provenance_ref`
- content digest

A contradiction must bind the same goal as the decision. Its resulting pin is always trust-labeled `EVIDENCE_ASSERTION`.

### 5. `DecisionContextPolicy`

The compiler owns a deterministic policy with one initial decision-context control:

- `critical_uncertainty_threshold = 0.55`

The threshold is content-addressed. Policy is configured on the compiler/runtime instance; a per-compilation call cannot weaken it. This repeats the anti-specification-gaming lesson from stress authority.

An unresolved `UncertaintyItem` becomes a `CRITICAL_UNKNOWN` pin when `risk_score >= critical_uncertainty_threshold`.

### 6. `GoalDesignDecisionContext`

Immutable content-addressed decision context:

- `context_id`
- `decision_receipt_id`
- `goal_id`
- `selected_option_id`
- `snapshot_digest`
- `integrity_receipt_id`
- `integrity_contract_digest`
- `policy_digest`
- exact `goal_digest`
- exact `scenario_set_digest`
- exact `option_set_digest`
- exact `evaluation_digest`
- exact `proof_state_digest`
- exact `uncertainty_state_digest`
- canonical tuple of `DecisionContextPin`
- canonical aggregate evidence refs

The context ID binds every source digest and every pin ID. Identical sealed inputs produce identical context identity.

### 7. `GoalDesignDecisionContextCompiler`

`compile(...)` accepts an already-authentic `DecisionReceipt`, the current `GoalIntegrityContract` and companion `GoalIntegrityReceipt`, plus the concrete goal/scenario/option/proof/uncertainty inputs whose digests must match the receipt.

Before producing any pins it must:

1. verify the decision receipt authenticity;
2. verify the integrity receipt binds the exact decision;
3. require integrity contract goal and digest to match the integrity receipt;
4. require the supplied goal to match `goal_id` and re-derive the exact historical `goal_digest`;
5. re-derive the exact scenario-set digest;
6. re-derive the exact option-set digest and evaluation digest;
7. require the selected option to exist and equal `selected_option_id`;
8. re-derive proof-state and uncertainty-state digests;
9. reject any mismatch before pin construction;
10. validate contradiction goal/evidence identity.

Receipt compatibility is critical. For historical v2 decisions with no assumption refs, the compiler uses the same base-schema projection used by `goal_design.py`; empty v3 fields must not perturb historical goal/option digests. For v3 truth-bound decisions, the full truth-capable goal/options remain part of identity.

### 8. Runtime seam

The strongest public seam lives on `GoalIntegrityRuntime`, because only that runtime can prove that the decision and integrity authority are still active and bound to the current contract.

`GoalIntegrityRuntime.compile_decision_context(...)`:

- resolves the decision record by receipt ID;
- requires decision lifecycle `ACTIVE`;
- resolves the integrity authority record and requires lifecycle `ACTIVE`;
- requires its contract to equal the current integrity contract for the goal;
- delegates to one configured `GoalDesignDecisionContextCompiler`;
- returns the immutable context without mutating historical decision or integrity receipts.

The runtime constructor accepts an optional compiler/policy once. There is no per-call policy override.

## Pin derivation

### Integrity pins

Each `GoalIntegrityClause` produces exactly one protected semantic pin. Mapping is one-to-one from `GoalIntegrityClauseKind` to the corresponding `DecisionContextPinKind`. The clause `provenance_ref`, contract digest, and integrity receipt ID remain visible.

### Champion and rivals

The option whose ID equals `decision_receipt.selected_option_id` produces the `CHAMPION` pin. Every other exact evaluated option produces a `RIVAL` pin. A caller cannot omit a rival without changing the option-set digest and causing compilation to fail.

### Open proofs

Every `ProofObligation` with status `OPEN` produces an `OPEN_PROOF` pin. The pin preserves `blocking`, claim, proof ID, and evidence refs. Satisfied/waived obligations remain represented in the receipt digest but are not context pins.

### Critical unknowns

Every unresolved uncertainty at or above the configured threshold produces a `CRITICAL_UNKNOWN` pin. Its salience is the bounded risk score, and the exact uncertainty-state digest remains the authority digest.

### Contradictions

Evidence-bearing contradiction inputs produce `CONTRADICTION` pins with `EVIDENCE_ASSERTION` trust. They cannot create or override any integrity pin, and their IDs are content-addressed.

## Fail-closed invariants

- Unknown or stale decision receipt: reject.
- Inactive/stale/superseded decision authority: runtime rejects.
- Missing/inactive integrity authority: runtime rejects.
- Historical integrity contract after supersession: reject.
- Goal, scenario, option, evaluation, proof, or uncertainty digest mismatch: reject.
- Selected option absent from exact option set: reject.
- Duplicate option/scenario/proof/uncertainty IDs: reject through existing canonical evaluation/state rules.
- Foreign contradiction goal: reject.
- Contradiction without evidence/provenance: reject.
- Per-call context policy override: no API exists.
- Caller cannot construct protected semantic pins through compiler inputs.
- Reordering semantically identical inputs cannot alter context identity.
- Context compilation has no side effects on decision, integrity, truth, reopening, or stress authority.

## Non-goals

- No natural-language inference of hidden goals or contradictions.
- No mutation of `ContextCapsule` in this wave.
- No replacement of Family-A truth authority.
- No replacement of Goal Integrity authority.
- No prompt formatting/rendering layer.
- No persistence database for contexts yet; content addressing permits later caching without changing identity.
- No changes to historical v1/v2/v3 decision receipt schemas.

## Verification strategy

TDD RED must use the current public runtime and fail behaviorally because `GoalIntegrityRuntime` cannot yet compile semantic decision context; a missing-module collection error is not accepted as the primary RED proof.

GREEN requires adversarial tests for:

- full exact pin derivation;
- deterministic identity under input reordering;
- option omission/substitution rejection;
- proof-state substitution rejection;
- uncertainty-state substitution rejection;
- foreign contradiction rejection;
- stale/superseded integrity authority rejection;
- protected pin provenance cannot be caller-injected;
- custom compiler policy is constructor-owned;
- v2-compatible empty-assumption digest projection;
- v3 truth-bound decision compatibility.

Acceptance gates:

- all `tests/test_goal_design*.py` on Python 3.11 and 3.12;
- Refoundation Epoch 0 on Python 3.11 and 3.13;
- R1.9 and R2.0i integrity gates;
- latest-main race guard and exact union rebuild if concurrent specialists touch the integration base;
- expected-head protected merge;
- actual-main post-merge Goal Design + R1.9 + R2.0i verification before CLOSED/GREEN.
