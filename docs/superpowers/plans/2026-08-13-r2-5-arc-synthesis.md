# R2.5 ARC Synthesis Implementation Plan

**Goal:** Build and measure a zero-neural-parameter generic ARC-AGI-2 grid synthesizer.

**Pinned ARC revision:** `f3283f727488ad98fe575ea6a5ac981e4a188e49`.

**Constraints:** keep 78,779,253 neural parameters; use only official training tasks during development; use generic reusable operators; produce at most two unique candidate grids per test input; freeze source and budgets before official public scoring.

## Task 1 — Grid model
Create `cogcoder/arc_grid.py` and `tests/test_r25_arc_grid.py`. TDD validation, dimensions, histograms, connected components, bounding boxes, crop, symmetry transforms, scale/repeat and overlay.

## Task 2 — Operator library
Create `cogcoder/arc_ops.py` and `tests/test_r25_arc_ops.py`. TDD deterministic operators for identity, D4 transforms, color replacement, crop/object selection, scaling, repetition, concatenation and component transforms. Each operator exposes a fixed complexity cost.

## Task 3 — Program search
Create `cogcoder/arc_synth.py` and `tests/test_r25_arc_synth.py`. TDD hierarchical exact-consistency search, signature deduplication and minimum-description-length ranking. Infer parameters from demonstration pairs rather than task names.

## Task 4 — Task adapter
Create `cogcoder/arc_eval.py`, `scripts/measure_r25_arc.py` and `tests/test_r25_arc_eval.py`. Parse official JSON tasks, generate no more than two outputs per test input and score complete-task exact matches.

## Task 5 — Training measurement
Create `.github/workflows/r25-training-only.yml`. Checkout the pinned official ARC repository and run only `data/training`. Use training results to improve generic operators and ranking.

## Task 6 — Freeze
Commit the exact source Git blob identities, operator vocabulary, search depth, candidate budget, per-task compute budget and two-output policy.

## Task 7 — Public measurement
After freeze, create a separate workflow for the official public set and run the frozen solver once. Preserve the exact result without changing the frozen candidate.

## Task 8 — Release
Publish provenance, measurement, claim boundary and integrity CI. Build a COMPLETE ZIP with source/tests/results/docs and exactly one current weight; verify its SHA-256 and persist ZIP, checksum and weight in Library.
