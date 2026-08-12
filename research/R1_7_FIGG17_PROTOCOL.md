# FIGG-17 Phase-A protocol

Date: 2026-08-12
Benchmark version: `nolane-figg17-v1`

FIGG-17 is a new R1.7 procedural interactive benchmark lineage. No R1.6 fresh task ID, seed namespace, or result is used for R1.7 optimization or model selection.

## Phase-A families

- `causal_laws`: three opaque actuators have state-conditional modular effects. The agent must learn action laws from interventions and plan to an explicit goal.
- `causal_switch`: opaque actuator mappings change after a publicly observable context transition. A competent agent must revise rather than persist with an obsolete law.
- `goal_inference`: the desired configuration is not present in the observation. Progress feedback and observed transitions provide the evidence needed to infer what future state is desirable.
- `composition_holdout`: demonstrations define a transformation program. Train/dev/fresh use distinct program-template sets; exact success is functional, not tied to a single textual rationale.

## Isolation

Split seed namespaces are disjoint:

- train: `17_100_000 + ...`
- dev: `17_200_000 + ...`
- fresh: `17_900_000 + ...`

`fresh` exists in the code so task IDs can be preregistered later, but Phase A development must not instantiate or evaluate it before the final R1.7 fresh lock.

## Metrics

Every task records exact completion plus action efficiency relative to a deterministic oracle reference. A solved episode receives `min(1, reference_actions / used_actions)`; unsolved episodes receive zero. This makes wasting actions visible instead of treating every solve as equivalent.

Additional model gates will record causal successor calibration, law-confidence quality, and preservation-family regressions.

## Controls

The benchmark runner supports exact oracle and deterministic random controls. Model gates must compare identical task IDs and action budgets.

## Public/private boundary

Policy inputs are limited to public JSON observations, public action descriptions/keys, recurrent state derived from public transitions, and public verifier feedback. Simulator internals are allowed only in oracle construction, teacher-label generation, and exact verification.
