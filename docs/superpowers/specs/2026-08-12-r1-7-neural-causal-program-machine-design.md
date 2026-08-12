# Nolane R1.7 — Neural Causal Program Machine (NCPM) Design

Date: 2026-08-12
Parent lineage: R1.6 EffectProgress fresh-best (`0a168806...`), not the dev-selected RuleProgramBroad checkpoint.

## Goal

Advance Nolane from a small neural cognitive agent that can bind action effects and estimate progress into a more general interactive reasoning system that can learn causal laws, represent explicit state-goal differences, synthesize latent subgoal/program sequences, and revise plans after feedback.

R1.7 must not tune against the consumed R1.6 fresh set. It receives a new procedural train/dev/fresh lineage and a new immutable preregistration before any R1.7 fresh evaluation.

## Architecture

### 1. Causal Law Slots

Maintain a small set of learned law slots representing hypotheses of the form:

`condition(state) + action -> structured effect distribution`

Inputs are public structured state sketches, dynamic semantic action embeddings, exact/contrastive observed-effect memory, and confidence/usage evidence. Slots update recurrently after interventions. The law representation is action-permutation equivariant and must not use benchmark-specific names.

The main objective is not one-step action classification. It is predicting counterfactual structured successor effects and uncertainty for all legal actions, with observed actions receiving stronger identification supervision.

### 2. Goal-Difference Workspace

Encode current and desired/favorable state evidence separately and construct relational difference tokens rather than collapsing them into a pooled state vector. The workspace must support partially known goals: target slots can be latent and updated from reward/progress/terminal evidence when no explicit target exists.

This component should expose typed residuals such as value mismatch, resource/precondition mismatch, unresolved object/field relation, and uncertainty, without hard-coded domain field names.

### 3. Latent Program Inducer

Use a recurrent latent program state to propose a short sequence of abstract subgoals / action-role decisions. Unlike R1.6 RuleProgramPrior, every refinement iteration receives predicted state transitions and verifier feedback. The program is therefore state-conditioned, not just position-conditioned.

The inducer uses shared dynamic-action scoring and latent recursion inspired by small recurrent reasoning architectures: a compact block is reused for multiple refinement iterations instead of scaling parameters linearly with reasoning depth.

### 4. Epistemic Executive

A small controller chooses between EXPLORE, MODEL, PLAN, EXECUTE, VERIFY, and REVISE modes. It receives uncertainty, law-slot disagreement, predicted goal-distance reduction, memory novelty, and verifier feedback. Exploration is chosen for expected information gain; execution is chosen when a plan has adequate confidence.

The controller also chooses recurrent compute depth. Extra depth is accepted only if an ablation demonstrates solve-rate/action-efficiency gain.

## Data and supervision

R1.7 uses procedural interactive worlds disjoint from R1.6 fresh. Training includes:

- multi-intervention causal system identification;
- compositional transformations with functionally equivalent programs;
- resource/precondition planning;
- hidden-goal environments where the agent must infer what terminal/progress evidence means;
- distractor actions and changing action order/opaque action keys;
- environment dynamics that require revising a previously valid plan;
- held-out compositions of primitives and held-out action semantics.

Supervision is public-observation grounded. Hidden simulator state may generate teacher trajectories or exact verifier labels, but must never enter policy/model inputs.

## Benchmark protocol

The new Frontier Interactive Generalization Gauntlet R1.7 (FIGG-17) measures:

1. completion rate;
2. action efficiency relative to an oracle/human-like reference;
3. causal-law identification accuracy;
4. counterfactual next-state calibration;
5. goal acquisition accuracy in implicit-goal worlds;
6. program/subgoal generalization on held-out compositions;
7. recovery after environment intervention/change;
8. compute efficiency / recurrent steps.

Controls: random, reactive/no-memory, no-causal-slots, no-goal-difference, no-program-inducer, no-recursion, scaffold-only where applicable, and the frozen R1.6 EffectProgress parent.

## Acceptance discipline

A module is retained only if it improves a preregistered held-out gate while preserving previously accepted capabilities. Offline teacher accuracy alone is not a capability gate.

R1.7 fresh is opened once after source/checkpoint/evaluator hashes and task seed IDs are locked and pushed to GitHub. No R1.7 weight or policy tuning is permitted after fresh opens.

## Parameter budget

Target effective size: 75–90M parameters. Hard research ceiling for R1.7: 96M. Capacity above the R1.6 parent must be justified by ablation; unused headroom is preferable to unproven modules.

## Persistence discipline

Every completed research step is immediately pushed to `Nolane-x/Nolane-AI/main` with code/protocol/result provenance. Binary checkpoints are persisted in incremental Library ZIPs when the GitHub connector cannot upload binary/LFS assets. At milestone completion, produce a complete delivery ZIP, verify it, expose it in chat, split it into Library-safe volumes if needed, and persist every part plus manifest and checksums.
