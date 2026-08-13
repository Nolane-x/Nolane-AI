# Nolane R1.7 Neural Causal Program Machine — Phase C Reality Report

Date: 2026-08-13

## Verdict

**ACCEPTED for a new bounded capability: learned operator induction + functional program composition.**

R1.7 Phase C does not claim AGI. It demonstrates that a ~75.39M-parameter Nolane cognitive system can learn public single-step operators, then compose them at inference time into programs longer than those used to train the operator model. The strongest evidence is a locked progression from train length-2 programs to held-out dev length-3 and untouched fresh length-4 programs.

## Frozen neural parent

- Checkpoint: `checkpoints/Nolane-R1.7-NCPM-OperatorExecutor.pt`
- SHA-256: `bfea6717c5a59b485934b2c9b0f3a48c65ac749a2f638a48a3cfedce6902a735`
- Effective parameters: **75,387,546**
- Functional Program Search parameters: **0**
- Fresh-time parameter updates: **0**

## What changed in Phase C

Phase C replaced failed next-action/template-prior approaches with a factorized program-solving architecture:

1. **Public structure extraction** identifies public numeric test vectors and demonstration pairs without relying on literal field names.
2. **Neural Operator Executor** learns `state vector + public action description -> successor vector` from single-step public transitions only.
3. **Functional Program Search** composes frozen learned operators and searches the shortest program that explains public demonstrations.
4. The inferred sequence is executed in the real interactive task and followed by the public submit action.

The search layer adds no neural parameters.

## Neural Operator Executor gate

Training data:
- FIGG-17 `composition_holdout/train`
- 200 fit worlds -> 1,000 single-step operator transitions
- 40 held-out train worlds -> 200 transitions
- hidden program/template identity was not an executor training target

Preregistered held-out transition gate:
- exact full-vector accuracy >= 98%
- element accuracy >= 99.5%
- each operator exact accuracy >= 95%

Accepted result (best epoch 18 of a completed 80-epoch protocol):
- exact full-vector: **99.5%**
- element: **99.5%**
- four operators: **100% exact**
- weakest operator: **97.5% exact**

## Functional Program Search gates

### Held-out TRAIN composition worlds

64 worlds, indices 522..585, programs length 2:
- demo-exact: **64/64 = 100%**
- real task solved: **64/64 = 100%**
- false-exact: **0/64**
- mean action efficiency: **1.0**

### DEV — unseen length-3 programs

60 worlds, six dev templates not present in the train template set:
- demo-exact: **59/60 = 98.33%**
- real task solved: **60/60 = 100%**
- false-exact: **0/60**
- each of six templates: **10/10 solved**
- mean action efficiency: **1.0**

Frozen normal parent policy on the same 60 dev worlds, with Functional Search disabled:
- **5/60 = 8.33%**

Paired absolute gain from inference structure: **+91.67 percentage points**.

### FRESH — unseen length-4 programs

Fresh was opened only after PRE_FRESH_LOCK_V2 bound checkpoint/source/evaluator hashes. No model or search tuning occurred after the lock.

60 fresh worlds, six length-4 templates:
- demo-exact: **60/60 = 100%**
- real task solved: **60/60 = 100%**
- false-exact: **0/60**
- each of six templates: **10/10 solved**
- mean action efficiency: **1.0**

Frozen normal parent policy on the already-consumed fresh set, evaluated only post-hoc for attribution:
- **0/60 = 0%**

Same weights + Functional Program Search:
- **60/60 = 100%**

Paired absolute gain: **+100 percentage points**.

The FIGG-17 Phase-C fresh set is now **consumed** and must never again be presented as an untouched test after any future tuning.

## Important negative results retained

R1.7 did not simply accumulate every attempted module.

- Goal-Difference progress model achieved strong MSE improvements, but scalar policy calibration did not change held-out decisions -> policy path rejected.
- Goal-conditioned linear advantage head reduced CE but did not improve causal argmax decisions -> rejected.
- CRGM role/goal matcher achieved correct role binding but failed the MSE+ranking gate -> rejected.
- Role-Effect Ranker improved `causal_switch` but degraded `causal_laws` -> rejected by per-family preservation gate.
- Latent Program Ranker failed corrected template-holdout transfer -> rejected.
- An earlier composition-teacher bug repeatedly selected the first oracle operation. It was found before accepted Program Search training, corrected by TDD, invalid caches were discarded, and prior composition-probe evidence based on that trajectory was explicitly withdrawn.

These failures are part of the research evidence and are preserved in results/GitHub provenance.

## Verification

After fresh evaluation:
- **81/81 R1.7 tests passed**
- **28/28 R1.1/R1.2/R1.6 protocol/integrity regressions passed**
- frozen checkpoint/source/evaluator hashes still matched PRE_FRESH_LOCK_V2

## What this proves

Within FIGG-17 composition tasks, Nolane R1.7 can:

- learn action/operator semantics from public transitions;
- model the effect of previously unseen action orderings;
- infer a functional transformation from examples;
- search over compositions of learned operators;
- generalize program depth from length 2 to length 3 and then untouched length 4;
- execute the inferred program successfully in the real interactive environment.

The dev/fresh comparison shows that the gain is not merely latent capacity already expressed by the base policy. The inference architecture is causally important.

## What this does NOT prove

This is not proof of:
- AGI;
- unrestricted code/program synthesis;
- arbitrary operator discovery in open-world repositories;
- transfer to ARC-AGI-3 or SWE-bench without direct evaluation;
- broad language intelligence equivalent to frontier 10B/100B models.

FIGG-17 has a bounded operator vocabulary and structured public demonstrations. Phase C is a strong mechanistic capability result inside that boundary.

## Next research direction

The next valid R1.7/R1.8 work should not tune against this consumed fresh set. The strongest path is to generalize the successful factorization:

`learn local dynamics -> infer symbolic/latent operators -> compose/search -> execute -> verify`

into the still-weak causal families, using **conditional operator hypotheses and context-indexed causal state machines** rather than additional generic scorers. A new benchmark split/world generator must be locked before claiming further fresh progress.
