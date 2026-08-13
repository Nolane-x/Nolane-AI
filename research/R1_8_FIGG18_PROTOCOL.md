# FIGG-18 v1 Benchmark Protocol

Date: 2026-08-13
Parent research lineage: R1.7 Phase C (`bfea6717c5a59b485934b2c9b0f3a48c65ac749a2f638a48a3cfedce6902a735`).

FIGG-18 is a new interactive causal benchmark namespace. It does not reuse FIGG-17 Phase-C fresh tasks, which are permanently consumed.

## Splits
- train base seed: `18_100_000`
- dev base seed: `18_200_000`
- fresh base seed: `18_900_000`

At benchmark-construction time only `train` and `dev` tasks may be instantiated. Fresh must remain unopened until a future pre-fresh lock binds source/checkpoint/evaluator hashes.

## Families
1. `conditional_regimes`: state-conditional actuator laws under a public regime cue.
2. `regime_switch`: three public regimes with repeated context return; stale evidence must be context-indexed.
3. `implicit_goal_regimes`: target hidden from observation; progress feedback is public.
4. `causal_prerequisites`: observable resource/gate prerequisites create subgoal structure.

## Integrity requirements
- action ordering shuffled per world;
- observation omits private laws and family identity;
- implicit-goal observation omits target;
- every sampled train/dev world must be oracle-solvable within budget;
- context-switch worlds must expose multiple regime changes and return to an earlier regime;
- exact simulator/oracle is the correctness source, never an LLM judge.

## Initial benchmark-construction evidence
- integrity tests: 7/7 pass;
- sampled oracle-solvability gate: 128/128 train/dev worlds solved;
- R1.7 regression suite: 81/81 pass after introducing FIGG-18.

No model has been trained on FIGG-18 at the time of this protocol record. FIGG-18 fresh is unopened.
