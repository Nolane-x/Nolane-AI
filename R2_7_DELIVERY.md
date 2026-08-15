# Nolane R2.7 — CodeWorld Generalist — Phase A Delivery

Date: 2026-08-15  
Status: **PHASE-A INTERNAL ACCEPTED / EXTERNAL CODING GATES PENDING**

## Why R2.7 exists

The project target is broad coding intelligence across the software lifecycle, not specialization on ARC. R2.6 produced a real development gain on ARC but no held-out gain, so R2.7 deliberately moves the main optimization target to cross-domain software-engineering control and external repository benchmarks.

## Neural change

R2.7 keeps the existing 78,779,253-parameter parent and adds one compact CodeWorld controller:

- new parameters: **622,147**
- candidate effective parameters: **79,401,400**
- growth: **0.7897%**
- Phase-A ceiling: **80,000,000**

The controller ranks generic coding actions (`inspect`, `search`, `read`, `reproduce`, `edit`, `test`, `diff`, `revert`, `finish`) from structured feedback. It is deliberately language/task agnostic.

## Internal transfer gate

Training uses a synthetic control-policy curriculum spanning 12 language labels and 8 software task types. Whole `(language, task_type)` pairs are withheld from training.

Actual Phase-A training run:

- train accuracy: **100.0%**
- held-out pair accuracy: **100.0%**
- split: pair-disjoint

This means the small controller learned the abstract coding-loop policy used by this curriculum and transferred it to unseen language/task combinations. It does **not** mean source-code competence is 100%.

## Safety/runtime change

A deterministic legality layer prevents the neural controller from finishing before targeted tests, full tests and diff review pass. Under a detected high-risk regression with one step left, recovery forces `revert` when available.

## One-weight candidate

`Nolane-R2.7-CodeWorld-Generalist-Phase-A-ONE-WEIGHT.pt`

- SHA-256: `16552d8565ba696dce3c2b853c27097f74e727bbfb8e2d6ff35064af308adcf5`
- bytes: `62,280,335`
- effective parameters: `79,401,400`
- parent SHA-256: `b1c2be66b6d42cc34b62a1c0960e47b13525d68126fa038b2ce9a11980b7f20e`

## What Phase B must prove

R2.7 becomes a meaningful broad-coding upgrade only after locked evaluations on multiple external axes such as real issue repair, feature addition, multi-file refactor, terminal work, multilingual repository tasks and evolving multi-turn requirements. The benchmark contract is in `benchmarks/codeworld/README.md`.

## Claim boundary

Phase A establishes a compact, parent-bound neural coding controller and internal combinatorial transfer. It does **not** establish AGI, human-level coding, superiority to frontier models, or any score on SWE-bench/FeatureBench/Terminal-Bench/Multi-SWE-bench/SWE-Bench ProMax.
