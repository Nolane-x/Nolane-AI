# R1.7 Neural Operator Executor + Functional Program Search protocol

Date: 2026-08-13
Benchmark: FIGG-17 v1.1
Parent lineage: accepted Goal-Difference/Causal-Law world stack. FIGG dev/fresh unopened.

## Motivation

The phase-conditioned Program Ranker failed held-out templates after correcting a composition teacher bug. It learned sequence/template priors rather than the transformation demonstrated by input/output examples.

R1.7 therefore factorizes program induction:

1. **Neural Operator Executor** learns reusable single-action state transitions from public interaction only.
2. **Functional Program Search** composes the learned operators and chooses the shortest action sequence whose predicted outputs fit all public demonstrations.

The executor never receives a hidden program/template label. Program search receives only demonstrations and dynamic action descriptions/embeddings.

## Field-name-agnostic public structure

Parameter-free JSON structure extraction must identify:
- the shallow public numeric test vector without inspecting literal key names;
- demonstration objects containing two equal-length numeric vector children, treated initially as an unordered pair.

Program search must consider both global demonstration orientations and may not use literal keys like `input`, `output`, `test_state`, or `goal` as semantic signals.

## Operator training data

FIGG `composition_holdout` **train only**.

Operation-executor fit worlds: indices `282..481` (200 worlds).
Held-out operation validation: indices `482..521` (40 worlds).
Seed: `170917`.

For each selected train world:
- start from the public test vector;
- for every legal non-submit action, clone the train simulator and execute the action once;
- collect public `(before vector, action description, after vector)`;
- no hidden program, goal, template id, or oracle action sequence enters executor input/target.

The same operation may appear in worlds whose hidden template is held out later; this is allowed because only its **single-step public transition law** is learned, not a program sequence.

## Executor architecture target

Small action-conditioned vector transition model, expected <1M new parameters:
- discrete numeric value embedding (support at least values 0..15);
- deterministic/small positional encoding;
- frozen dynamic action embedding from the existing action encoder;
- small two-layer contextual sequence model over vector positions;
- per-position categorical next-value logits.

Old checkpoints must load with the executor behavior-neutral because no policy path uses it before the standalone gate.

## Executor internal gate

On operation-validation worlds 482..521:
1. exact full-vector next-state accuracy must be >= 0.98;
2. per-element accuracy must be >= 0.995;
3. every non-submit operator kind must have exact-vector accuracy >= 0.95;
4. no parent parameter receives gradient;
5. effective candidate remains below 96M.

No program-search metric is allowed to compensate for a failed executor gate.

## Functional program search gate

Only after executor acceptance.

Use new FIGG train worlds `522..585` (64 worlds):
- template ids 0..5 are available only as development sanity worlds;
- **program generalization gate is templates 6 and 7**, 16 worlds total, unseen as program sequences during any program-policy optimization;
- executor weights remain frozen.

Search sequences over all non-submit dynamic actions with horizon 1..4. Score sequences only by learned-executor consistency with all public demonstration pairs. Evaluate both global demo orientations and prefer the shortest exact-consistency hypothesis.

Program gate on template 6/7 worlds:
1. inferred sequence applied through the real environment solves >= 14/16 tasks;
2. exact hidden-program sequence match is reported diagnostically but is **not** required when a functionally equivalent sequence solves the task;
3. no hidden program/goal is used to select the sequence;
4. no FIGG dev/fresh use.

Passing these gates creates a reusable model-based program-induction primitive. Policy integration and held-out FIGG dev still require separate preregistration.
