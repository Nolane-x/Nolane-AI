# R1.8 Conditional Causal State Machine Design

## Goal
Evolve the frozen R1.7 Phase-C system into an agent that can identify, track, revise, and exploit **conditional causal laws** under public context changes, while preserving the accepted learned-operator composition capability.

## Research boundary
R1.8 starts from `checkpoints/Nolane-R1.7-NCPM-OperatorExecutor.pt` (`bfea6717c5a59b485934b2c9b0f3a48c65ac749a2f638a48a3cfedce6902a735`, 75,387,546 effective params). FIGG-17 Phase-C fresh is consumed and may never be used as untouched evidence again. R1.8 uses a new benchmark namespace and new split seeds. Parameter ceiling remains 96M, but Phase D may add at most 4M trainable parameters before an ablation proves a larger increase is necessary.

## Why this architecture
R1.6/R1.7 repeatedly showed that predictive MSE, teacher-forced accuracy, and generic residual scorers do not guarantee closed-loop control. Phase C succeeded when the problem was factorized into local dynamics learning plus explicit composition/search. R1.8 applies the same lesson to causal control:

`observe -> identify context/state -> maintain law hypotheses -> certify reliability -> explore or plan -> execute -> verify -> revise belief`.

The controller must abstain from model-based planning when its law hypotheses are unreliable. This mirrors the current research lesson that a world model is useful only when its representation is control-sufficient and when planning can decline to act on unreliable predictions.

## FIGG-18 benchmark
New version: `nolane-figg18-v1`. New seed bases: train `18_100_000`, dev `18_200_000`, fresh `18_900_000`.

Four families:

1. `conditional_regimes`: three opaque actuators; each action has state-dependent effects and a public regime cue. Regime changes are deterministic but vary by world. The same actuator can affect different coordinates/deltas across regimes.
2. `regime_switch`: a public context marker changes multiple times within one episode. Old evidence becomes stale unless indexed by context. The agent must detect change and re-identify affected laws.
3. `implicit_goal_regimes`: goal vector is not shown. Only public progress feedback is available. The agent must jointly infer goal direction and conditional dynamics.
4. `causal_prerequisites`: state includes controllable variables plus public prerequisite flags/resources. Some actions only have their intended effect when observable prerequisites hold, forcing subgoal planning.

All worlds must be oracle-solvable. Public observations contain everything needed in principle; hidden simulator fields may create teacher/oracle labels but are never neural inputs. Action order is shuffled per world. Train/dev/fresh use disjoint task IDs and seeds.

Metrics: completion, human/oracle-normalized action efficiency, information actions used, stale-law mistakes after context switch, and closed-loop success. Exact oracle is the correctness gate; no LLM judge.

## R1.8 architecture

### 1. Public Context Fingerprint
A deterministic structured fingerprint from public numeric/categorical atoms. It must be invariant to JSON key renaming where semantics are preserved and must not read benchmark family names. It identifies whether evidence belongs to the same causal regime.

### 2. Context-Indexed Causal Evidence Memory
Non-parametric memory stores, per dynamic action, tuples of `(context fingerprint, pre-state sketch, observed role-relative effect, count, consistency)`. Retrieval selects evidence from the nearest compatible context. Evidence from stale contexts is not silently reused.

### 3. Conditional Neural Law Prior
A shared neural transition prior predicts role-relative action effects from current public state sketch, context fingerprint, dynamic action embedding, and retrieved evidence. Target size: 1.5-3.0M parameters. It is trained only on FIGG-18 train worlds with counterfactual targets available from the train simulator.

### 4. Reliability Certificate
A parameter-free or tiny calibrated module combines evidence count, evidence consistency, neural-vs-memory agreement, context distance, and predicted failure. It emits `reliable[action]` and an episode-level planning confidence. If confidence is low, model-based planning is forbidden and the controller selects a safe information-gathering action.

### 5. Active Experiment Selector
When no certified plan exists, choose an action maximizing expected hypothesis discrimination / coverage while respecting known failure risk and budget. It must never use hidden laws.

### 6. Certified Causal Planner
When laws are certified, perform bounded search over the public structured state abstraction. Planning uses context-conditioned effects and observable prerequisite transitions. If a predicted transition disagrees with reality, invalidate the affected hypothesis and return to exploration.

## Gate sequence
1. FIGG-18 integrity + oracle gate on train/dev only.
2. Evidence-memory invariants with no neural changes.
3. Conditional law prior held-out train transition gate: beat persistence/evidence baselines per family.
4. Reliability calibration: planning advice must improve or abstain; forced-planning ablation must not be better than certified planning.
5. Closed-loop dev gate against frozen R1.7 parent and scaffold-only controls.
6. Only after all hashes are locked, open FIGG-18 fresh once.

## Required controls
- random controller;
- frozen R1.7 normal policy;
- evidence-memory-only controller;
- neural-prior-only controller;
- full controller with certificate disabled (forced planning);
- full certified R1.8.

## Claim boundary
Passing FIGG-18 proves bounded interactive causal adaptation under conditional regimes. It does not prove AGI, unrestricted causal discovery, or parity with frontier 10B/100B models without direct same-protocol comparison.
