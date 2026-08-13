# R1.8 Conditional Causal State Machine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new FIGG-18 benchmark and a context-indexed, reliability-certified causal controller on top of frozen R1.7 Phase C.

**Architecture:** Keep the 75.39M Phase-C checkpoint frozen initially. Add a new benchmark, parameter-free context/evidence memory, then a small conditional transition prior. Only certified laws may drive bounded planning; uncertain states force active experimentation. Every capability claim requires held-out closed-loop gates and controls.

**Tech Stack:** Python 3, PyTorch, pytest, deterministic procedural simulators, SHA-256 provenance, GitHub `main`, ChatGPT Library recovery ZIPs.

## Global Constraints
- R1.7 Phase-C fresh is consumed and never reused as untouched evidence.
- FIGG-18 fresh remains unopened until a pre-fresh lock is committed.
- Hard parameter ceiling: 96,000,000 effective parameters.
- Phase-D neural additions before ablation: <=4,000,000 parameters.
- No hidden simulator field may enter neural/controller inputs.
- Each completed research step: verify -> push GitHub `main` -> continue.
- Milestone close: complete ZIP + Library persistence.

---

### Task 1: FIGG-18 benchmark and integrity gates
**Files:** Create `cogcoder/r18_benchmark.py`; `tests/test_r18_benchmark.py`; `research/R1_8_FIGG18_PROTOCOL.md`.
**Interfaces:** `make_r18_task(family, split, index) -> R18Task`, `oracle_plan(task) -> list[int]`, `lock_r18_tasks(tasks) -> dict`.
- [ ] Write failing tests for split disjointness, shuffled action order, public/private boundary, context switching, implicit-goal feedback, prerequisite behavior, and oracle solvability.
- [ ] Verify RED.
- [ ] Implement minimal deterministic benchmark.
- [ ] Verify >=128 sampled train/dev worlds are oracle-solvable and tests GREEN.
- [ ] Push benchmark + protocol to GitHub.

### Task 2: Context fingerprint and evidence memory
**Files:** Create `cogcoder/r18_causal_memory.py`; `tests/test_r18_causal_memory.py`.
**Interfaces:** `public_context_fingerprint(observation_text) -> Tensor`; `ConditionalEvidenceMemory.update(...)`; `retrieve(...)`.
- [ ] Write RED tests for rename invariance, stale-context isolation, action permutation equivariance, and no-history abstention.
- [ ] Implement parameter-free memory.
- [ ] Run focused R1.8 + R1.7 regressions.
- [ ] Push source/tests/evidence.

### Task 3: Conditional neural law prior
**Files:** Modify `cogcoder/neural_system2.py`; `cogcoder/r17_training.py`; create `cogcoder/r18_training.py`; tests `test_r18_conditional_law.py`.
**Interfaces:** `conditional_law_scores(state_sketch, context, actions, evidence) -> predicted_effect, confidence`.
- [ ] RED tests: old checkpoint behavior-neutral, action permutation equivariance, <=4M new params, FIGG-18 train-only collector.
- [ ] Implement shared conditional transition prior zero-neutral to policy.
- [ ] Train only new law parameters on FIGG-18 train; checkpoint selected by held-out train transition gate.
- [ ] Require per-family non-degradation versus persistence/evidence baseline.
- [ ] Push and Library-persist accepted checkpoint or negative verdict.

### Task 4: Reliability certificate and active experiment selector
**Files:** Create `cogcoder/r18_controller.py`; `tests/test_r18_controller.py`.
**Interfaces:** `certify_laws(...)`, `select_experiment(...)`.
- [ ] RED tests: unreliable predictions must abstain; context shift invalidates stale plan; safe unseen action preferred for information; action permutation preserved.
- [ ] Implement certificate from consistency/context distance/model-memory agreement.
- [ ] Calibrate thresholds only on FIGG-18 train-internal split.
- [ ] Ablate forced planning vs certified planning.
- [ ] Push result.

### Task 5: Certified planner and closed-loop dev gate
**Files:** `cogcoder/r18_planner.py`; `scripts/evaluate_r18.py`; tests `test_r18_planner.py`.
**Interfaces:** bounded plan/explore loop over public state abstraction.
- [ ] TDD successor simulation, prerequisite handling, replanning after prediction mismatch.
- [ ] Preregister dev task IDs/hashes and controls.
- [ ] Evaluate random, R1.7 parent, memory-only, neural-only, forced-planning, full certified controller.
- [ ] Require full controller to improve aggregate solved and causal efficiency without family regression.
- [ ] Push all traces/results.

### Task 6: Pre-fresh lock, fresh gate, and delivery
**Files:** `results/R1_8_PRE_FRESH_LOCK.json`, Reality Report, final manifest/delivery docs.
- [ ] Verify source/checkpoint/evaluator hashes and regressions.
- [ ] Commit immutable pre-fresh lock before task instantiation.
- [ ] Run fresh exactly once; no post-fresh tuning.
- [ ] Produce complete ZIP, run `unzip -t`, SHA-256 it.
- [ ] Upload complete ZIP or split volumes to Library.
- [ ] Push final provenance to GitHub.
