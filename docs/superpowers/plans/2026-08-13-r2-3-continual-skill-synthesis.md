# R2.3 Continual Skill Synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a zero-neural-parameter continual skill system that induces bounded transformations from demonstrations, persists and revises them, and transfers them to unseen episodes.

**Architecture:** Add a deterministic bounded skill synthesizer, a versioned persistent skill registry, and a continual runtime around frozen R2.2. Evaluate on KFIGG-23 curricula against a persistent replay baseline under identical demonstration exposure.

**Tech Stack:** Python 3.12, dataclasses, existing restricted epistemic instruction set, pytest, JSON research locks.

## Global Constraints
- Keep neural effective parameters exactly 78,779,253.
- Add exactly 0 neural trainable parameters in R2.3.
- Use only the existing bounded arithmetic instruction set.
- TRAIN-only protocol selection; DEV then one-time FRESH with committed source hashes.
- No hidden answer or hidden generator description may enter public runtime state.
- Current one-weight remains `Nolane-R2.0i-78.8M-STRONGEST-ONE-WEIGHT.pt`.

### Task 1 — Bounded demonstration-to-skill synthesizer
Create `cogcoder/skill_synthesis.py` and `tests/test_r23_skill_synthesis.py`. Test one-step and multi-step induction, deterministic shortest selection, budget failure and instruction allow-list before implementation. Implement breadth-by-depth deterministic bounded search and rerun focused tests.

### Task 2 — Versioned persistent skill registry
Create `cogcoder/skill_memory.py` and `tests/test_r23_skill_memory.py`. Test persistence, independent-skill retention, version supersession, provenance collision rejection and rollback before implementation. Implement immutable skill artifacts and bounded competence counters.

### Task 3 — Continual runtime integration
Create `cogcoder/r23_runtime.py` and `tests/test_r23_runtime.py`. Test learn/apply, composition, revision and exact R2.2 behavior preservation before implementation. Integrate the synthesizer and registry without changing the neural stack.

### Task 4 — KFIGG-23 continual-transfer benchmark
Create `cogcoder/kfigg23.py`, `scripts/evaluate_r23_continual.py` and `tests/test_r23_kfigg23.py`. Test hidden-answer separation, identical exposure, deterministic generation and metric correctness before implementation. Add a persistent replay baseline and R2.3 solver.

### Task 5 — Locked admission and release
Create pre-DEV, DEV, pre-FRESH, FRESH, current-best and reality-report artifacts plus `scripts/verify_r23_release.py` and `.github/workflows/r23-integrity.yml`. Select protocol only on TRAIN; open DEV once; if it passes, lock unchanged source and open FRESH once. Acceptance requires candidate >=85%, gain >=20 pp, retention >=90%, revision >=90%, composition >=80%, integrity failures =0. Publish accepted source/tests/results to GitHub main. Build a COMPLETE ZIP with exactly one weight, verify archive/SHA, and persist ZIP/checksum/one-weight to ChatGPT Library.
