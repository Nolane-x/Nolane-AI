# Goal/Design Stress-World and Reversibility Authority Design

## Status

Implementation authority for the next D. Goal / Design hardening wave. The design is intentionally companion-based: it strengthens admission without rewriting historical v1/v2/v3 decision receipt identity.

## Problem

The current Goal/Design gate requires costly or irreversible choices to name an explicit alternative and include a counterfactual/adversarial scenario. That proves that a scenario label exists, not that the selected option was genuinely stress-tested. A caller can satisfy the gate with a decorative tag while providing no quantified severity, provenance, tail exposure, recovery quality, containment evidence, or reversibility comparison.

This is a specification-gaming surface. For decisions that are costly to unwind or impossible to unwind, scenario syntax must not substitute for evidence-bearing stress authority.

## Goals

1. Require quantified, evidence-bearing stress-world authority for `COSTLY_REVERSIBLE` and `IRREVERSIBLE` admissions.
2. Preserve exact historical v1/v2/v3 decision receipt identity rules.
3. Bind stress authority to the exact goal, scenario set, option set, selected option, and decision class so tokens cannot be replayed across changed decision inputs.
4. Make tail exposure and recovery/containment properties explicit and policy-controlled.
5. Add a reversibility frontier so a selected option cannot be strictly dominated by an alternative in both robust performance and reversibility without an explicit authority justification.
6. Keep D as the admission/control-plane authority. It consumes evidence and deterministic evaluations; it does not become Family-A truth authority or Family-G evaluation ownership.

## Non-goals

- No new terminal-goal semantics.
- No mutation of historical decision receipts.
- No probabilistic world-model inference in D.
- No replacement of Evaluation-family stress infrastructure.
- No cryptographic signer hierarchy in this wave; tokens are deterministic proof-carrying assessment artifacts, not privileged identity credentials.

## Architecture

### 1. Stress world evidence

`StressWorldEvidence` binds one existing `DesignScenario` to a declared stress kind and quantitative challenge metadata:

- `world_id`
- `scenario_id`
- `kind`: `COUNTERFACTUAL | ADVERSARIAL | TAIL | FAILURE`
- `plausibility` in `[0,1]`
- `severity` in `[0,1]`
- non-empty `evidence_refs`
- content digest

A stress world cannot invent an unscored scenario: `scenario_id` must exist in the exact decision scenario set, and every evaluated option must already carry a utility for it through existing Goal/Design evaluation rules.

### 2. Recovery / containment evidence

`RecoveryProfile` is option-specific and evidence-bearing:

- `option_id`
- `rollback_ref` (for costly-reversible choices)
- `containment_ref` (for irreversible choices)
- `recovery_probability`
- normalized `recovery_cost`
- normalized `recovery_latency`
- `residual_harm`
- non-empty `evidence_refs`
- content digest

For `COSTLY_REVERSIBLE`, the profile rollback reference must exactly match `DesignOption.rollback_ref`. For `IRREVERSIBLE`, an explicit containment reference is required because rollback cannot be assumed.

`recovery_score = recovery_probability * (1-recovery_cost) * (1-recovery_latency) * (1-residual_harm)`.

### 3. Policy

`StressPolicy` contains deterministic configurable thresholds. Default policy:

- costly reversible requires at least one `ADVERSARIAL` or `COUNTERFACTUAL` world;
- irreversible requires at least one `ADVERSARIAL`/`COUNTERFACTUAL` world and at least one `TAIL`/`FAILURE` world;
- every required world has evidence;
- costly selected option: maximum stress exposure <= `0.60`, recovery score >= `0.12`, residual harm <= `0.50`;
- irreversible selected option: maximum stress exposure <= `0.45`, recovery/containment score >= `0.08`, residual harm <= `0.35`.

Stress exposure for world `w` and selected option utility `u_w` is:

`exposure_w = plausibility_w * severity_w * (1 - u_w)`.

Thresholds are policy, not hidden constants, and their digest participates in authority identity.

### 4. Reversibility frontier

The existing Goal/Design evaluation already computes `robust_score` and coarse `optionality` from decision class. Stress authority computes a two-axis frontier over `(robust_score, reversibility_score)` where:

- detailed `RecoveryProfile.recovery_score` is used when present;
- otherwise the existing class optionality is used as the coarse fallback (`1.0`, `0.5`, `0.0`).

The selected non-trivial option is blocked if another explicit option is weakly better on both axes and strictly better on at least one. This is a fail-closed Pareto check over performance and exit capacity, separate from the goal-objective Pareto check already present.

### 5. Admission token

`StressAdmissionToken` is content-addressed and binds:

- exact raw goal digest;
- exact canonical scenario-set digest;
- exact canonical option-set digest;
- selected option id and decision class;
- policy digest;
- stress-world digests;
- recovery-profile digests;
- selected stress exposure / recovery score;
- reversibility-frontier ids;
- blockers and authorization result.

`GoalDesignStressAuthority.authorize(...)` returns a token. `verify_token(...)` re-derives the complete assessment from the supplied decision inputs and rejects stale, rebound, or tampered tokens.

### 6. Coherence-plane integration

Public `GoalDesignCoherencePlane.admit_decision()` gains optional `stress_token`.

- `REVERSIBLE`: existing behavior remains exact when no token is supplied.
- `COSTLY_REVERSIBLE` and `IRREVERSIBLE`: missing, unauthorized, stale, or mismatched token is a blocker before the historical base admission is called.
- The historical base receipt algorithm is not changed. Therefore accepted decision receipt identity remains determined by existing v1/v2/v3 rules.

This deliberately makes the public D authority surface enforce the new gate rather than relying only on the runtime wrapper.

### 7. Runtime integration and companion receipt

`GoalDesignRuntime` owns a `GoalDesignStressAuthority`. `admit()` accepts `stress_worlds`, `recovery_profiles`, and optional `stress_policy`. For non-trivial choices it mints the admission token, passes it through the coherence plane, then emits a content-addressed `DecisionStressReceipt` binding the accepted `decision_receipt_id` to the exact stress token.

The companion receipt provides audit linkage without altering the decision receipt.

## Fail-closed invariants

- Unknown/duplicate stress world or scenario identities are rejected.
- Required stress kinds cannot be satisfied by one world pretending to have multiple kinds.
- Required evidence refs cannot be empty.
- Non-finite/out-of-range metrics are rejected.
- Recovery profiles cannot be rebound to a different option.
- Costly rollback evidence must match the option rollback reference exactly.
- Irreversible containment evidence is mandatory.
- Token verification re-derives input, policy, evidence, risk and frontier digests.
- An unauthorized token can never cross the admission boundary.
- A token for one selected option cannot authorize another.
- A token generated before any goal/scenario/option change becomes stale.

## Compatibility

Historical receipt verification remains unchanged. Reversible admissions with no stress token follow the exact existing path. Existing costly/irreversible callers must provide quantified stress inputs; this is an intentional authority hardening, not a receipt migration.

## Verification

TDD must first prove the current bypass: a decorative adversarial tag alone can admit a non-trivial decision. GREEN acceptance requires:

- focused stress authority tests;
- all `tests/test_goal_design*.py` on Python 3.11 and 3.12;
- Refoundation Epoch 0;
- R1.9 and R2.0i integrity gates;
- exact latest-main race guard and union rebuild if concurrent specialists advance main;
- actual-main post-merge Goal Design/integrity verification before closure.