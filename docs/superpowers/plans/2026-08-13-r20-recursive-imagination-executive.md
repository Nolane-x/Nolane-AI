# R2.0 Recursive Imagination Executive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate a <79M Nolane R2.0 that recursively imagines 1/2/4/8/16-step futures with shared weights, adaptively allocates inference compute, and improves exact closed-loop solve rate over the locked shallow parent baseline.

**Architecture:** R2.0 freezes the accepted 78,214,173-parameter R1.9 parent and reuses its ConditionalLaw + FrontierRollout world-model as the transition primitive. A <=700k-parameter `RecursiveImaginationExecutive` scores imagined action trajectories, carries a recurrent executive state, predicts confidence/stop decisions, and selects reasoning depth; recursive depth and bounded beam search add compute but no depth-specific trainable copies.

**Tech Stack:** Python 3.12, PyTorch, pytest, deterministic procedural FIGG-18 tasks, SHA-256 provenance, JSON/Markdown locks and results, GitHub Actions.

## Global Constraints

- Parent deployment SHA-256: `6081a38f65142ae06dc36cba1c9a567a9d0754c08d683d89a8e76f7aade9c52a`.
- Parent effective parameters: `78,214,173`.
- R2.0 total effective parameters must be `<79,000,000`.
- R2.0 trainable delta target must be `<=700,000` parameters and absolute maximum is `785,826`.
- R1.9 parent parameters are frozen for the entire milestone.
- Training uses FIGG-18 `train` worlds only.
- Fit indices are `400..463` per family, validation `464..479`, untouched train gate `480..499`.
- Inference features may contain public observations and neural predictions only; hidden task state/oracle labels are forbidden.
- Supported imagination depths are exactly `{1,2,4,8,16}`.
- Fresh data remains unopened until train gate + DEV + pre-fresh lock complete.
- R1.9 consumed fresh examples cannot be reused as untouched R2.0 evidence.
- User-facing deployment output is one strongest standalone weight.

---

### Task 1: Recursive imagination engine

**Files:**
- Create: `model/r2.0/cogcoder/r20_imagination.py`
- Test: `model/r2.0/tests/test_r20_imagination.py`

**Interfaces:**
- Consumes: frozen R1.9 `FrontierRolloutHead`, public state/context/action embeddings, parent predicted effects.
- Produces: `ImaginationTrace`, `ActionImagination`, `RecursiveImaginationPlanner.imagine_actions(...)`.

- [ ] **Step 1: Write failing tests for shared-depth behavior**

Tests must require:

```python
planner = RecursiveImaginationPlanner(parent, rollout, beam_width=3)
result = planner.imagine_actions(public_features, depths=(1, 2, 4, 8, 16))
assert set(result.depths) == {1, 2, 4, 8, 16}
assert result.parameter_count == 0
assert result.used_hidden_task_fields is False
```

Also require deterministic results for identical public inputs, bounded beam width, legal action indices only, finite values/uncertainties, and no trainable depth embeddings.

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
PYTHONPATH=model/r2.0 pytest -q model/r2.0/tests/test_r20_imagination.py
```

Expected: import/module failure because `r20_imagination` does not exist.

- [ ] **Step 3: Implement minimal recursive planner**

Implement immutable dataclasses for imagined nodes/traces, deterministic depth features, bounded beam expansion, repeated use of the same R1.9 transition head, uncertainty accumulation, and state-sketch updates. Do not access simulator internals.

- [ ] **Step 4: Verify GREEN**

Run the test command above and require zero failures.

- [ ] **Step 5: Commit**

Commit source + tests with message `feat: add parameter-free R2.0 recursive imagination engine`.

### Task 2: Compact integrated executive

**Files:**
- Create: `model/r2.0/cogcoder/r20_executive.py`
- Test: `model/r2.0/tests/test_r20_executive.py`

**Interfaces:**
- `RecursiveImaginationExecutive.forward(...) -> dict[str, Tensor]`
- `init_state(batch_size: int) -> Tensor`
- `r20_parameter_count(module) -> int`

Required outputs:

```python
{
    "action_logits": Tensor[B, A],
    "next_state": Tensor[B, H],
    "stop_logit": Tensor[B],
    "success_probability": Tensor[B],
    "depth_logits": Tensor[B, 5],
}
```

- [ ] **Step 1: Write failing tests**

Require permutation equivariance across action rows, recurrent-state continuity, all outputs finite, `0 <= success_probability <= 1`, exactly five depth logits, and `r20_parameter_count(executive) <= 700_000`.

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=model/r2.0 pytest -q model/r2.0/tests/test_r20_executive.py
```

Expected missing-module failure.

- [ ] **Step 3: Implement compact shared executive**

Use small projections + one shared GRUCell. Score every action with shared weights; do not allocate an action-count-specific classifier matrix. Include scalar depth/budget/progress/uncertainty features and output shared action logits plus recurrent state, stop, confidence, and depth logits.

- [ ] **Step 4: Verify GREEN and exact parameter budget**

Require the test to pass and write the exact count to stdout/result metadata.

- [ ] **Step 5: Commit**

Commit message: `feat: add compact R2.0 recursive imagination executive`.

### Task 3: Train-only feature collector and training gate

**Files:**
- Create: `model/r2.0/cogcoder/r20_training.py`
- Create: `model/r2.0/scripts/train_r20_recursive_executive.py`
- Create: `research/R2_0_PRETRAIN_LOCK.json`
- Test: `model/r2.0/tests/test_r20_training.py`

**Interfaces:**
- `collect_r20_episode(parent, rollout, task) -> tuple[R20TrainingRow, ...]`
- `train_r20_epoch(...) -> float`
- `evaluate_r20_rows(...) -> dict`
- `save_r20_delta(...)`, `load_r20_delta(...)`

- [ ] **Step 1: Write failing isolation tests**

Require collector to reject `dev` and `fresh`, training rows to omit `private_state`, `oracle_plan`, hidden solution fields, and parent tensors to remain unchanged after an optimizer step.

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=model/r2.0 pytest -q model/r2.0/tests/test_r20_training.py
```

- [ ] **Step 3: Implement training collector**

Generate action labels from a copied training-world oracle only during label construction. Store only public/neural features + target action/depth/success labels. Use fixed fit/validation ranges from Global Constraints.

- [ ] **Step 4: Implement trainer/checkpoint format**

Freeze parent, optimize only executive delta, bind parent SHA-256, exact parameter count, architecture, seed, protocol, epoch metrics and tensor digest.

- [ ] **Step 5: Train and select checkpoint only by preregistered validation metric**

Use deterministic seed `200020`. Stop only after the preregistered epoch budget; select the best validation checkpoint afterward. No train-gate peeking during checkpoint selection.

- [ ] **Step 6: Reload and reproduce validation**

Require candidate metric reproduction within `1e-9` where deterministic and exact parent tensor digest equality before/after.

- [ ] **Step 7: Commit**

Commit source/tests/lock/internal result with message `research: train locked R2.0 recursive executive delta`.

### Task 4: Closed-loop controller + ablations

**Files:**
- Create: `model/r2.0/cogcoder/r20_closed_loop.py`
- Create: `model/r2.0/scripts/evaluate_r20_gate.py`
- Test: `model/r2.0/tests/test_r20_closed_loop.py`

**Interfaces:**
- `run_r20_episode(..., mode="adaptive" | "fixed_depth_2" | "fixed_depth_8" | "greedy_parent" | "random") -> dict`
- `evaluate_r20_gate(...) -> dict`

- [ ] **Step 1: Write failing tests**

Require identical tasks/seeds across modes, deterministic random baseline, no hidden fields, finite step count, exact `solved` result from public task termination, and adaptive depth limited to `{1,2,4,8,16}`.

- [ ] **Step 2: Verify RED**

Run the focused test and confirm missing behavior.

- [ ] **Step 3: Implement controller**

Each real environment step recomputes public features, imagines candidate futures, selects requested depth, scores actions, acts once, observes real public feedback, and updates recurrent state/evidence memory.

- [ ] **Step 4: Run untouched train gate indices `480..499`**

Run all preregistered modes on all four families. Store task-level rows plus aggregate/family metrics.

- [ ] **Step 5: Apply acceptance gate without tuning**

Accept only if parameter/freeze/integrity requirements pass and recursive/adaptive mode satisfies the solve-rate improvement rule from the design. If rejected, record rejection and do not open DEV.

- [ ] **Step 6: Commit accepted/rejected train-gate evidence**

Commit message must state `accept` or `reject` accurately.

### Task 5: Calibration + DEV/FRESH locks

**Files:**
- Create: `model/r2.0/cogcoder/r20_calibration.py`
- Create: `research/R2_0_PRE_FRESH_LOCK.json` only after DEV acceptance
- Create: `research/r2.0/results/r2_0_dev.json`
- Create: `research/r2.0/results/r2_0_fresh.json` only after lock
- Test: `model/r2.0/tests/test_r20_calibration.py`

**Interfaces:**
- `brier_score(...)`
- `expected_calibration_error(..., bins=10)`
- `high_confidence_error_rate(..., threshold=0.8)`

- [ ] **Step 1: TDD exact calibration metrics**

Use hand-computed fixtures and test invalid confidence ranges.

- [ ] **Step 2: If train gate accepted, run DEV on locked unseen DEV range**

Do not update model/evaluator/depth thresholds after seeing DEV except to reject the candidate. If DEV shows catastrophic regression, reject and keep FRESH closed.

- [ ] **Step 3: Write pre-fresh lock**

Bind candidate SHA, parent SHA, evaluator hashes, fresh indices, beam width, depths, adaptive thresholds, inference budget and all ablations.

- [ ] **Step 4: Open FRESH once**

Run the exact locked evaluator once. Mark fresh consumed immediately. No subsequent tuning is allowed for that checkpoint.

- [ ] **Step 5: Commit calibration + DEV/FRESH evidence**

Reality report must distinguish neural, algorithmic-search and workspace/tool contributions.

### Task 6: Standalone one-weight R2.0 artifact

**Files:**
- Create: `model/r2.0/cogcoder/r20_standalone.py`
- Create: `CURRENT_ONE_WEIGHT_R2_0.json`
- Test: `model/r2.0/tests/test_r20_standalone.py`

**Interfaces:**
- `load_r20_standalone(path) -> (parent, rollout, executive, metadata)`

- [ ] **Step 1: Write failing loader/reproducibility tests**

Require one file to reconstruct all neural modules and reproduce locked gate outputs on a deterministic smoke subset.

- [ ] **Step 2: Build FP32 standalone bundle**

Bundle R1.9 parent + rollout + accepted R2.0 delta + metadata.

- [ ] **Step 3: Convert storage tensors to FP16 and re-evaluate**

Accept FP16 storage only if closed-loop solve decisions on the smoke/gate subset are unchanged or any metric degradation remains inside the preregistered tolerance.

- [ ] **Step 4: Verify exact SHA-256 and size**

Write checksum and manifest. The user-facing artifact is the single strongest one-weight file.

### Task 7: GitHub CI, reality report, ZIP and Library persistence

**Files:**
- Create: `research/R2_0_REALITY_REPORT.md`
- Create: `research/R2_0_CURRENT_BEST.json`
- Create: `scripts/verify_r20_release.py`
- Create: `.github/workflows/r20-integrity.yml`
- Modify: `README.md`

- [ ] **Step 1: Run focused R1.9 + R2.0 tests from a clean cache state**

Record exact pass/failure counts; do not claim the historical full suite is clean unless it actually finishes clean.

- [ ] **Step 2: Add CI provenance gate**

CI checks parameter arithmetic, parent/delta hashes, lock/result consistency, source compilation and benchmark-claim contract.

- [ ] **Step 3: Publish practical source/results/docs/manifests directly to GitHub `main`**

Do not claim binary GitHub publication unless raw bytes are actually present there.

- [ ] **Step 4: Create COMPLETE delivery ZIP**

Include source, tests, locks, results, docs, one strongest weight, checksums and recovery metadata. Exclude transient caches.

- [ ] **Step 5: Verify ZIP**

Run `unzip -t` and compute SHA-256.

- [ ] **Step 6: Persist to ChatGPT Library**

Upload the current one-weight and COMPLETE ZIP; if file size requires it, split recovery volumes with an exact reassembly manifest.

- [ ] **Step 7: Verify GitHub Actions**

Read the actual workflow run conclusion before claiming CI success.

## Self-review

- Spec coverage: architecture, parameter ceiling, train isolation, closed-loop ablations, adaptive depth, calibration, DEV/FRESH discipline, one-weight deployment, GitHub/ZIP/Library persistence are all mapped to tasks.
- Placeholder scan: no `TODO`, `TBD`, or unspecified implementation steps remain.
- Interface consistency: `RecursiveImaginationPlanner`, `RecursiveImaginationExecutive`, `R20TrainingRow`, gate modes and standalone loader names are consistent across tasks.
- Scope: external ARC/HLE/FrontierMath/Terminal-Bench execution remains a later milestone after R2.0 passes local closed-loop gates; R2.0 itself builds the prerequisite long-horizon executive rather than mixing unrelated external benchmark engineering into the same acceptance gate.
