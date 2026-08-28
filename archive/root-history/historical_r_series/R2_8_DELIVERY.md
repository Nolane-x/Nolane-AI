# Nolane R2.8 — Repository World Model + Epistemic Active Debugging

Date: 2026-08-15
Status: **PHASE-A INTERNAL GATE PASSED / EXTERNAL CODING GATES PENDING**

## Why this milestone exists

R2.7 introduced a compact coding-loop controller, but its Phase-A curriculum largely mapped workflow stage to action. R2.8 removes that shortcut as evidence: the same loop state and the same base controller scores can now produce different actions when repository uncertainty or dependency topology differs.

## Architecture added

- language-agnostic repository graph with dependency/test impact closure;
- normalized competing fault hypotheses updated only from public evidence;
- binary-probe expected information gain based on Shannon entropy;
- action utility combining R2.7 controller score, information gain, posterior target coverage, progress, cost, and graph-derived edit risk;
- R2.7 safety legality remains authoritative;
- node/hypothesis renaming invariance gate to prevent identifier memorization.

## Neural parameter accounting

- R2.7 parent: **79,401,400** effective neural parameters;
- R2.8 new neural parameters: **0**;
- R2.8 candidate: **79,401,400** effective neural parameters.

R2.8 deliberately does not create a new neural checkpoint. It carries the R2.7 one-weight and adds a cognition-time world-model runtime.

Parent weight: `Nolane-R2.7-CodeWorld-Generalist-Phase-A-ONE-WEIGHT.pt`

- SHA-256: `16552d8565ba696dce3c2b853c27097f74e727bbfb8e2d6ff35064af308adcf5`

## Locked Phase-A result

The preregistered protocol contains four adversarial routing cases. Pairs deliberately share identical `CodingLoopState` values but require different correct actions because either epistemic uncertainty or dependency blast radius changes.

- cases: **4**;
- exact action accuracy: **4/4 = 100%**;
- full node + hypothesis rename invariance: **4/4 = 100%**;
- new neural parameters: **0**;
- result SHA-256: `c4f8e2045c7d63102e9245966428165f4f373f673b9f874eb0daea7f8db6db09`.

This is intentionally a small architecture gate, not a coding benchmark score.

## What R2.8 now enables

A future coding agent can ask: *which experiment most reduces uncertainty about the fault?* and *how much of the repository could this edit affect?* instead of following a fixed inspect→search→edit sequence. This is a prerequisite for robust long-horizon debugging under changing evidence.

## Remaining major gap

R2.8 still does **not** provide a general arbitrary source-code patch generator. The next independent research axis should add language-agnostic patch/program search with executable verification, then test it on fresh real repositories.

## External gate roadmap

External coding claims remain locked. The next evidence stage should use fresh/broad executable repository tasks, prioritizing contamination-resistant issue repair, multilingual repair, feature-level development, and terminal work. Candidate benchmark families include SWE-bench-Live, SWE-rebench V2, Multi-SWE-bench, FeatureBench, and Terminal-Bench.

## Claim boundary

R2.8 Phase A does not establish AGI, real-world repository issue-resolution performance, arbitrary code generation, or parity/superiority to frontier models. It establishes only the implemented repository-world-model and epistemic-routing behaviors under the locked internal protocol.
