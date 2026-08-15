# R2.8 Repository World Model + Epistemic Active Debugging Design

Date: 2026-08-15

## Problem

R2.7 proved a compact controller can learn a generic coding-loop ordering, but its Phase-A target is largely a function of workflow stage. That means the held-out language×task-pair result does not establish semantic repository transfer. R2.7 also does not by itself provide a general source-code patch generator.

## Goal

Build a zero-new-neural-parameter cognitive layer that represents repository structure, maintains competing debugging hypotheses, chooses evidence-gathering actions by expected information gain, and routes R2.7 proposals using repository evidence rather than fixed stage alone.

## Non-goals

- Do not claim AGI, frontier-model parity, or external benchmark performance.
- Do not add language-specific heuristics to inflate a synthetic score.
- Do not implement arbitrary patch generation in R2.8; that is the next independent research axis after world-model routing is verified.
- Do not increase neural parameter count in this milestone.

## Architecture

1. `RepoWorldGraph` stores language-agnostic nodes and typed edges for files, symbols, tests, configs, packages, and runtime components. It exposes dependency/impact traversal and edit-risk estimation.
2. `HypothesisLedger` stores mutually competing fault hypotheses over repository nodes and updates their probabilities from public evidence.
3. `EpistemicProbe` models the likelihood of a binary observation under each hypothesis. `ActiveDebugger` scores legal actions using expected entropy reduction, posterior target coverage, progress value, cost, and regression risk.
4. `choose_epistemic_action` keeps R2.7 safety legality but can choose different actions for the same `CodingLoopState` and same base neural proposals when repository evidence differs.
5. Phase-A evidence uses adversarial routing cases with identical workflow stage but different hypothesis structure. Node names and language labels are irrelevant to the scoring logic, blocking trivial ID memorization.

## Parameter policy

Parent effective neural parameters: 79,401,400.
New R2.8 neural parameters: 0.
Candidate effective neural parameters: 79,401,400.

Any later parameter increase must be justified by fresh-repository transfer evidence rather than internal synthetic gain alone.

## Acceptance boundary

R2.8 Phase A is an architecture/cognition gate only. Promotion to an external coding claim remains forbidden until executable fresh-repository evaluation is run under a locked protocol. Preferred future gates are contamination-resistant or broad repository benchmarks such as SWE-bench-Live, SWE-rebench V2, Multi-SWE-bench, FeatureBench, and Terminal-Bench.
