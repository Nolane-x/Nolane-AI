# C11 Counterfactual Policy Qualification — Design

## Status

Architectural continuation of C. Reasoning / Invention after C10 governed metareasoning-policy evolution.

C11 advances `external.reasoning_invention` from component revision `0.0.4` to `0.0.5` without changing any existing C1–C10 wire schema. It adds one additive schema: `reasoning-policy-qualification-v1`.

Nolane World 0.12.0 remains design provenance only. Nolane AI owns the runtime contracts, identities, authority boundaries and verification rules.

## Problem

C10 correctly prevents self-promotion: policy revisions are monotonic constraints, development/holdout evidence is disjoint, shadow metrics remain Pareto-separated, fresh-context review is explicit, and adoption/rollback requires external authority.

One important epistemic gap remains. `PolicyShadowEvaluation` binds aggregate parent and candidate metric vectors to the same declared holdout episode set, but the aggregate artifact does not prove that:

1. parent and candidate were evaluated on matched task/environment/world/evidence contexts;
2. the same holdout episodes were not selectively reused or regrouped after outcomes were visible;
3. aggregate improvement is not a context-mix or Simpson's-paradox artifact;
4. a policy qualified in one regime is not silently applied in another regime;
5. tail regressions are not hidden behind a favorable aggregate vector.

This is a scope and attribution problem, not another learning problem.

## Design choice

C11 adds a separate immutable qualification protocol rather than widening C10 policy objects.

The protocol has four layers:

1. **Exact trial context** — an opaque, content-addressed snapshot of the external context in which a parent/candidate comparison is meaningful.
2. **Matched counterfactual trial** — parent and candidate policy outcomes are paired under the same exact context and produce a derived effect vector where positive values always mean improvement.
3. **Regime qualification** — multiple independent matched trials are checked for tail regressions and exact regime compatibility; no scalar average can erase a bad trial.
4. **Applicability receipt** — an already externally adopted policy is either qualified for an exact context or explicitly `ABSTAIN_OUT_OF_SCOPE`.

C11 does not route policies, mutate a current-policy pointer, issue adoption authority, or execute reasoning actions.

## Alternatives considered

### A. Add context fields directly to C10 `PolicyShadowEvaluation`

Rejected. It would change an accepted C10 serialized identity/schema and still leave per-trial matching underspecified.

### B. Introduce a mutable policy router

Rejected. A router would become a new hidden governor and could silently expand C authority into D/E/runtime policy selection.

### C. Counterfactual qualification as a separate additive evidence protocol

Selected. It preserves C10 identities, keeps attribution auditable, and makes out-of-scope use fail closed without owning deployment authority.

## Canonical objects

### `PolicyTrialContext`

An exact comparison context with opaque external references:

- `task_id`
- `objective_id`
- `environment_id`
- `world_revision_id`
- `ontology_revision_id`
- `evidence_root_id`
- `cognitive_library_digest`
- `action_class_id`
- `initial_frontier_id`
- `context_tag_ids`

All IDs are non-empty. Tags are canonicalized as a duplicate-free set. The object receives a content-derived `context_id`.

These references do not transfer Truth, Memory, D, E, Cognitive Library or Assurance authority to C11. They only bind the context that external authorities supplied.

### `PolicyRegime`

A policy regime contains only dimensions that may legitimately be shared across several matched tasks:

- `environment_id`
- `world_revision_id`
- `ontology_revision_id`
- `cognitive_library_digest`
- `action_class_id`
- `required_context_tag_ids`

A context matches a regime only when all exact dimensions match and the required tag set is a subset of the context tags. There are no wildcards and no fuzzy matching.

### `PolicyEffectVector`

The effect vector is derived from parent/candidate `PolicyMetricVector` values. Every dimension is normalized so positive means better:

- `decision_accuracy_gain`
- `information_gain_delta`
- `uncertainty_reduction_delta`
- `cost_reduction`
- `residual_risk_reduction`
- `regression_count_reduction`

The caller cannot supply this vector when binding a trial.

### `MatchedPolicyTrial`

A matched trial binds:

- exact C10 `proposal_id`;
- exact C10 `shadow_evaluation_id`;
- parent and candidate policy IDs;
- one `PolicyTrialContext`;
- one parent episode ID and one distinct candidate episode ID;
- parent/candidate `PolicyMetricVector` values;
- the derived `PolicyEffectVector`;
- explicit `improved_metric_ids` and `regressed_metric_ids` derived from the effect vector;
- a content-derived `trial_id`.

Both episode IDs must come from the exact C10 shadow holdout set. Development episodes are never valid trial evidence.

A trial is `PARETO_NON_REGRESSING` only if no metric regresses and at least one metric improves. A no-change result remains inconclusive rather than being relabeled as progress.

### `PolicyRegimeQualification`

Qualification consumes:

- the exact C10 proposal and shadow evaluation;
- the exact C10 policy adoption receipt;
- one `PolicyRegime`;
- at least two matched trials.

All trials must bind the same proposal/shadow/parent/candidate lineage and match the declared regime.

Qualification rejects:

- reused parent/candidate episode authority across trials;
- duplicate trial identities;
- fewer than two distinct task IDs;
- any tail-regressing trial;
- any trial whose context falls outside the regime;
- a candidate policy not equal to the externally adopted policy;
- an adoption receipt bound to another proposal or shadow evaluation.

Qualification succeeds only when every matched trial is Pareto non-regressing and at least one improvement exists in the evidence set. There is no aggregate weighted score.

### `PolicyApplicabilityReceipt`

`evaluate_policy_applicability` consumes an exact qualification and an exact `PolicyTrialContext`.

Verdicts:

- `QUALIFIED_FOR_CONTEXT`
- `ABSTAIN_OUT_OF_SCOPE`

The receipt binds the policy, regime, qualification and context IDs. Out-of-scope is evidence, not an exception that callers are encouraged to ignore.

The receipt authority is `qualification_evidence_only`.

## Invariants

### Q1 — Matched context before attribution

Parent and candidate outcomes may be compared only inside one exact `PolicyTrialContext`.

### Q2 — No holdout laundering

Each parent/candidate episode pair must be drawn from the C10 holdout set and episode authority cannot be reused across qualification trials.

### Q3 — Tail regressions are blocking

One regressing matched trial blocks qualification even when another trial improves strongly. C11 never averages away a bad tail.

### Q4 — No hidden scalar utility

Effect dimensions remain separate. Qualification uses Pareto/non-regression logic only.

### Q5 — Scope is exact and explicit

Environment, world revision, ontology revision, Cognitive Library digest and action class must match the regime exactly. Required regime tags must be present. No wildcard or optimistic substitution exists.

### Q6 — Adoption remains external

C11 can qualify only a policy already represented by a C10 `PolicyAdoptionReceipt`. It cannot create adoption or rollback authority.

### Q7 — Applicability is not routing authority

`QUALIFIED_FOR_CONTEXT` is evidence that the declared context lies inside the validated regime. It does not mutate a current policy, choose a policy for the caller, or authorize D/E actions.

### Q8 — Out-of-scope fails closed

A context outside the qualification regime yields `ABSTAIN_OUT_OF_SCOPE`.

### Q9 — Canonical replay

Every C11 artifact round-trips through `to_state` / `from_state`; forged derived IDs and non-canonical set ordering are rejected.

### Q10 — Existing schemas remain stable

`reasoning-invention-v1`, every C8 schema, `reasoning-episode-v1`, and `reasoning-policy-evolution-v1` retain their current serialized identity contracts.

## Versioning

- component: `external.reasoning_invention`
- target component version: `0.0.5`
- canonical revision: `5`
- new schema: `reasoning-policy-qualification-v1`

All modules in the Reasoning/Invention family continue to report the same component revision after cutover.

## TDD acceptance

RED must be demonstrated on the latest-main-integrated branch by committing behavior/adversarial C11 tests before `reasoning_policy_qualification.py` exists.

GREEN requires:

1. exact-context matched trials;
2. derived effect vectors;
3. C10 holdout binding;
4. duplicate/reused episode rejection;
5. tail-regression blocking;
6. regime mismatch rejection;
7. externally adopted-policy binding;
8. explicit out-of-scope abstention;
9. canonical round-trip and forged-ID rejection;
10. bool/NaN/infinity/duplicate-ID hardening;
11. coherent `0.0.5` / revision `5` cutover;
12. source scan proving no mutable policy router, execution authority, Assurance minting, model write, Memory/Truth write or capability-promotion backdoor;
13. hosted Refoundation acceptance on Python 3.11 and 3.13 against the exact final PR synthetic merge;
14. latest-main race guard with `behind_by = 0` before certification.

## Non-goals

C11 does not prove universal causal effect, discover unknown regimes, infer external truth, certify oracle competence, deploy policies, execute actions, modify D goals/plans, mutate E state, write Memory/Truth/Cognitive Library state, mint Assurance, promote capabilities, accept transfer, or modify Neural state.
