# R2.59 Active Diagnostic Repository Probe Synthesis Implementation Plan

> **For agentic workers:** Use RED→GREEN TDD and preserve the strict claim boundary.

**Goal:** Replace fixed hidden counterexample ordering with deterministic active diagnostic input selection over executable repository patch hypotheses.

**Architecture:** Generate a finite content-addressed probe set, score probes by candidate behavior partition quality without target labels, query only the best probe under a hard oracle budget, and require independent exhaustive verification before accepting a unique patch.

**Tech Stack:** Python 3.11/3.13, pytest, R2.52 repository patch candidates/compiler, GitHub Actions, Nolane World 0.8.0.

## Task 1 — Probe identity and active solver
- Create `tests/test_r259_active_repository_probes.py` first.
- Require content-addressed IDs, input-order-independent enumeration, maximal discrimination, candidate-ID/order invariance, no-informative-probe abstention, and budget exhaustion.
- Verify RED before implementation.
- Create `cogcoder/r259_active_repository_probes.py`.
- Verify focused GREEN.

## Task 2 — Frozen repository benchmark
- Create `tests/test_r259_active_repository_probe_benchmark.py` first.
- Create `benchmarks/kfigg/r259_active_repository_probe_transfer.py`.
- Reuse the protected R2.52 six-episode heldout repository family without changing its target patches.
- Generate legal probe inputs from the fixed Cartesian domain independently of target outputs.
- Compare active one-query selection against a target-independent hash-selected one-query baseline and a passive initial-only baseline.
- Require exhaustive 2,401-input final verification and zero false accepts.
- Freeze exact result only after deterministic rerun equality.

## Task 3 — Evidence and CI
- Freeze `R2_59_PHASE_A_RESULT.json` from measured output.
- Add `.github/workflows/r259-active-repository-probes.yml`.
- Run R2.59 focused tests, recompute frozen result, and run protected R2.58→R2.41 lineage.
- Run Python 3.11/3.13 focused matrix.
- Publish commit statuses only on success.

## Task 4 — External falsification before readiness movement
- Seek an independently sourced executable function/repository candidate family not used to design R2.59.
- Require target-output-free probe generation, matched selection-oracle budget, causal active-vs-random/passive gain, zero false accepts, and independent heldout verification.
- If clean external evidence is unavailable or fails, keep readiness at R2.58's 47.8/100 rather than inflating the score.

## Task 5 — Nolane World and release
- Run Nolane World 0.8.0 adversarial audit on the exact capability commit.
- Preserve W5=false unless the runtime itself earns convergence.
- Freeze delivery, verification, world audit, manifest, and release-bundle workflow only after hosted evidence is clean.
- Persist final complete ZIP + SHA-256 + evidence to Library.
