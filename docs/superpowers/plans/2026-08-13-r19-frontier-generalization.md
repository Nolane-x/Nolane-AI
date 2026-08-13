# R1.9 Frontier-Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a <2M-parameter recurrent rollout residual head, prove held-out two-step world-model improvement over the R1.8 additive baseline, add frontier benchmark adapters, and package the full recovered AI lineage with real weights.

**Architecture:** R1.8 remains immutable. R1.9 is a small delta checkpoint containing `FrontierRolloutHead`; its recurrent cell is weight-shared across program positions and refinement iterations. FIGG-19 generates exact two-step counterfactual targets from R1.8 procedural worlds and compares the new head to the parent-only additive rollout baseline on identical rows.

**Tech Stack:** Python 3, PyTorch, pytest, JSON/Markdown manifests, ZIP/SHA-256, GitHub Contents API for text artifacts.

## Global Constraints

- Parent SHA-256 is `400fc43ef46c9b6c7664703b49c0de7896b49eb728939423288b74847cb27c16`.
- New trainable parameters must be <2,000,000.
- Candidate effective parameters must be <79,000,000.
- R1.9 training may consume FIGG-19 `train` only; `dev` and `fresh` stay unopened during training.
- Parent parameters are frozen and their values must not change.
- No private benchmark answers or hidden simulator fields may enter policy/model inputs.
- Capability claims must distinguish measured internal results from unrun external >100B comparisons.

---

### Task 1: FIGG-19 two-step rollout contract

**Files:**
- Create: `cogcoder/r19_rollout.py`
- Test: `tests/test_r19_rollout.py`

**Interfaces:**
- Consumes: `R18Task`, structured observation encoders, R1.8 conditional-law outputs.
- Produces: `RolloutRow`, `collect_rollout_rows(...)`, `additive_parent_baseline(...)`, exact counterfactual targets.

- [ ] Write tests that require train-only collection, exact two-step simulator targets, deterministic split seeds, non-submit program enumeration, and no hidden/private fields in row objects.
- [ ] Run the tests and verify they fail because `cogcoder.r19_rollout` does not exist.
- [ ] Implement the smallest collector satisfying those contracts.
- [ ] Run the tests and verify they pass.

### Task 2: FrontierRolloutHead and parameter isolation

**Files:**
- Create: `cogcoder/r19_frontier.py`
- Test: `tests/test_r19_frontier.py`

**Interfaces:**
- `FrontierRolloutHead(state_dim=128, context_dim=64, action_dim=640, hidden_dim=256, refine_steps=3)`
- `forward(state, context, program_actions, parent_effects, goal=None) -> dict[str, Tensor]`
- `configure_r19_training(head) -> list[str]`

- [ ] Write tests for tensor shapes, action/program permutation consistency, deterministic parameter count, and <2M trainable parameters.
- [ ] Run and observe the expected missing-module failure.
- [ ] Implement shared projections, a relation encoder, one shared GRU refinement cell, residual-effect/value/uncertainty heads, and zero-initialized residual output.
- [ ] Run tests and keep R1.8 regressions green.

### Task 3: R1.9 training and acceptance gate

**Files:**
- Create: `cogcoder/r19_training.py`
- Create: `scripts/train_r19_frontier_rollout.py`
- Test: `tests/test_r19_training.py`

**Interfaces:**
- `evaluate_r19_rows(parent, head, rows) -> metrics`
- `train_r19_epoch(parent, head, rows, optimizer) -> float`
- `r19_internal_gate(metrics) -> bool`
- Delta checkpoint includes parent SHA, head state, parameter counts, protocol, and metrics.

- [ ] Write tests that require parent parameters to remain frozen, baseline/candidate evaluation on identical rows, all-family gate semantics, and checkpoint parent binding.
- [ ] Run and verify expected failures.
- [ ] Implement evaluator/trainer/checkpoint helpers.
- [ ] Train on preregistered train indices and select the best internal-validation epoch.
- [ ] Reload the saved delta checkpoint and reproduce validation metrics within numerical tolerance.

### Task 4: Frontier >100B evaluation contract

**Files:**
- Create: `benchmarks/frontier100b/README.md`
- Create: `benchmarks/frontier100b/harness.py`
- Create: `tests/test_frontier100b_harness.py`

**Interfaces:**
- exact ARC grid scorer;
- normalized closed-answer scorer;
- executable verifier result schema;
- comparison record that refuses `hard_for_gt100b=true` without a named evaluated >100B reference run.

- [ ] Write tests for scoring correctness and claim-boundary enforcement.
- [ ] Run and observe failure before implementation.
- [ ] Implement pure scoring/harness utilities without bundling private datasets.
- [ ] Run tests.

### Task 5: Provenance, publication, and complete delivery

**Files:**
- Create: `research/R1_9_REALITY_REPORT.md`
- Create: `research/R1_9_CURRENT_BEST.json`
- Create: `WEIGHTS_MANIFEST_R1_9.json`
- Create: `.gitattributes`
- Create: `scripts/publish_weights_lfs.sh`
- Modify: `README.md`

- [ ] Run R1.8 + R1.9 focused tests and record exact results.
- [ ] Generate SHA-256 for all included checkpoints and the R1.9 delta.
- [ ] Produce a complete ZIP containing source, tests, results, docs, base checkpoints, R1.8 parent, and R1.9 delta.
- [ ] Verify the ZIP with `unzip -t` and SHA-256.
- [ ] Upload the complete ZIP plus checksum to ChatGPT Library.
- [ ] Publish all text source/docs/manifests to `Nolane-x/Nolane-AI` `main`; publish binary weights through LFS only when a binary-capable GitHub channel exists, never via fabricated text placeholders.
