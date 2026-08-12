# Nolane R1.7 Phase A — Recovery, FIGG-17, and Causal Law Slots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover the locked R1.6 research tree, establish a new uncontaminated interactive benchmark lineage, and add a small recurrent Causal Law Slot subsystem that improves counterfactual system identification over the frozen R1.6 EffectProgress parent.

**Architecture:** R1.7 Phase A leaves the accepted R1.6 neural trunk, PSR, and EffectProgress policy frozen as the parent. It adds a law-slot memory that updates from public structured transitions and scores counterfactual action effects through shared, action-permutation-equivariant operators. The new benchmark uses a new seed namespace, explicit action-efficiency metrics, and preregistered train/dev/fresh isolation.

**Tech Stack:** Python 3, PyTorch, pytest, JSON procedural environments, GitHub provenance, ChatGPT Library recovery volumes.

## Global Constraints

- R1.6 consumed fresh tasks must never be used for R1.7 training or model selection.
- R1.7 effective parameter target is 75–90M; hard ceiling is 96M.
- Policy inputs may contain public observations, public action descriptions/keys, recurrent memories derived from public transitions, and verifier feedback only.
- Hidden simulator state may create teacher/verifier labels but may never enter model inputs.
- Dynamic action behavior must remain permutation-equivariant and independent of fixed action slots.
- Every completed research step must be pushed to `Nolane-x/Nolane-AI/main` before the next experiment.
- Every binary candidate checkpoint that matters must be persisted in an incremental Library ZIP because the current GitHub connector cannot upload LFS/release binaries.
- No R1.7 fresh evaluation before a source/checkpoint/evaluator/task-ID lock is pushed to GitHub.

---

### Task 1: Recover and audit the R1.6 final tree

**Files:**
- Materialize: `/Nolane/R1.6-Final/Nolane-R1.6-COMPLETE.part-00` through `part-20`
- Verify: `/Nolane/R1.6-Final/FINAL_VOLUMES_MANIFEST.json`
- Restore into: `/mnt/data/Nolane-R1.7-NCPM-WORK/r16_parent/`
- Create: `research/R1_7_PARENT_AUDIT.json`

**Interfaces:**
- Consumes: Library volume file IDs and the final ZIP SHA `1ab75a90f56b88389fe2c0b4e03d15fd58310cd756986a32e1ffdccefd1e7101`.
- Produces: a restored source tree and exact path/hash for the R1.6 EffectProgress checkpoint `0a168806...`.

- [ ] **Step 1: Materialize all 21 final volumes**

Use `files.materialize` in batches of at most five into `/mnt/data/Nolane-R1.7-NCPM-WORK/recovery_parts/`.

- [ ] **Step 2: Reassemble and verify the final ZIP**

Run:
```bash
cat recovery_parts/Nolane-R1.6-COMPLETE.part-* > r16-final.zip
sha256sum r16-final.zip
unzip -t r16-final.zip
```
Expected SHA-256: `1ab75a90f56b88389fe2c0b4e03d15fd58310cd756986a32e1ffdccefd1e7101` and `No errors detected`.

- [ ] **Step 3: Extract and locate parent source/checkpoint**

Run:
```bash
mkdir -p r16_parent
unzip -q r16-final.zip -d r16_parent
find r16_parent -name 'Nolane-R1.6-NS2-EffectProgress.pt' -o -name 'neural_system2.py'
```

- [ ] **Step 4: Verify parent checkpoint and baseline tests**

Run the focused R1.6 test sets documented in the final Reality Report and verify the EffectProgress checkpoint SHA matches the final manifest.

- [ ] **Step 5: Write parent audit JSON and push it**

Record archive SHA, source root, parent checkpoint path/SHA, test counts, and known frozen source/test drift. Push `research/R1_7_PARENT_AUDIT.json` to `main`.

---

### Task 2: Create FIGG-17 benchmark namespace and integrity tests

**Files:**
- Create: `source/cogcoder/r17_benchmark.py`
- Create: `source/tests/test_r17_benchmark_integrity.py`
- Create: `source/scripts/run_r17_figg17_gate.py`
- Create: `research/R1_7_FIGG17_PROTOCOL.md`

**Interfaces:**
- Produces: `make_r17_task(family: str, split: str, index: int) -> Task`, `evaluate_r17_episode(...) -> dict`, and deterministic task IDs under namespace `figg17:`.

- [ ] **Step 1: Write failing integrity tests**

Tests must assert:
```python
assert make_r17_task("causal_laws", "train", 0).task_id != make_r17_task("causal_laws", "dev", 0).task_id
assert make_r17_task("causal_laws", "dev", 0).task_id != make_r17_task("causal_laws", "fresh", 0).task_id
assert "hidden" not in json.dumps(task.public_observation()).lower()
```
Add tests for action-order permutation, deterministic seeds, exact verifier behavior, and action-efficiency accounting.

- [ ] **Step 2: Run tests and confirm RED**

Run:
```bash
pytest source/tests/test_r17_benchmark_integrity.py -q
```
Expected: import/function failures because `r17_benchmark.py` does not exist.

- [ ] **Step 3: Implement benchmark families**

Implement at least four Phase-A families:
1. `causal_laws`: opaque actions with state-dependent/modular effects requiring multiple interventions;
2. `causal_switch`: dynamics change after a public context event, requiring belief revision;
3. `goal_inference`: no explicit goal vector; progress/terminal evidence reveals desired state;
4. `composition_holdout`: compositions of primitives with held-out order/combination.

Every environment exposes only public JSON state/action information to the agent.

- [ ] **Step 4: Implement oracle and random controls**

The oracle uses simulator internals only outside policy inputs and returns minimal/near-minimal action count. Random control uses legal actions only and fixed evaluation seeds.

- [ ] **Step 5: Run integrity tests and push**

Run the new benchmark tests plus the R1.6 benchmark-integrity regression set. Push code, tests, and `R1_7_FIGG17_PROTOCOL.md` before model work.

---

### Task 3: Add Causal Law Slot state and neutral model plumbing

**Files:**
- Modify: `source/cogcoder/neural_system2.py`
- Modify: `source/cogcoder/neural_system2_training.py`
- Create: `source/tests/test_r17_causal_law_slots.py`

**Interfaces:**
- Produces:
```python
@dataclass
class CausalLawState:
    slots: Tensor          # [B, K, H]
    confidence: Tensor     # [B, K]
    usage: Tensor          # [B, K]

model.init_causal_law_state(batch_size: int, device) -> CausalLawState
model.update_causal_laws(state_sketch, action_embeddings, action_index, observed_delta, law_state) -> CausalLawState
model.causal_law_scores(state_sketch, action_embeddings, law_state) -> dict
```

- [ ] **Step 1: Write RED tests**

Tests must require:
- zero evidence leaves confidence low;
- updating action `i` changes only evidence attributable to action `i` through shared addressing;
- action permutation permutes outputs identically;
- legacy EffectProgress checkpoint loads with law contribution exactly neutral;
- total parameter count remains <96M.

- [ ] **Step 2: Run RED tests**

Run:
```bash
pytest source/tests/test_r17_causal_law_slots.py -q
```
Expected failures: missing `CausalLawState` / model methods.

- [ ] **Step 3: Implement minimal law-slot module**

Use K=8 slots, H=256, shared projections, recurrent gated updates, and a zero-initialized policy/world-model residual scale. Do not add benchmark-family embeddings or fixed action IDs.

- [ ] **Step 4: Run model + checkpoint regression tests**

Run:
```bash
pytest source/tests/test_r17_causal_law_slots.py source/tests/test_neural_system2.py source/tests/test_neural_system2_checkpoint.py -q
```
Expected: all pass.

- [ ] **Step 5: Push neutral architecture before training**

Record parameter count and source hashes. Push source/test/provenance before optimizer work.

---

### Task 4: Train law slots on train-only counterfactual dynamics

**Files:**
- Create: `source/scripts/train_r17_causal_laws.py`
- Create: `source/tests/test_r17_causal_law_training.py`
- Create: `research/R1_7_CAUSAL_LAW_TRAINING_PROTOCOL.md`

**Interfaces:**
- Consumes FIGG-17 train tasks only.
- Produces checkpoint `checkpoints/Nolane-R1.7-NCPM-CausalLaws.pt` and `results/r1_7_causal_laws_internal.json`.

- [ ] **Step 1: Write optimizer-scope and leakage RED tests**

Assert optimizer names are only `causal_law_*` plus explicitly listed neutral scales; verify fresh/dev task constructors are never called by the trainer.

- [ ] **Step 2: Run RED tests**

Expected: missing trainer helpers.

- [ ] **Step 3: Implement batched training**

Train on counterfactual successor-delta, failure/done, and law-confidence targets. Use train-internal validation with disjoint indices. Parent trunk/PSR/EffectProgress stay frozen.

- [ ] **Step 4: Internal gate**

Candidate proceeds only if it beats an action-conditioned persistence/effect-memory baseline on held-out train tasks and does not reduce parent action accuracy on preservation families.

- [ ] **Step 5: Persist and push candidate before dev**

Create an incremental ZIP containing checkpoint, protocol, internal results, source hashes, and tests. Upload it to Library. Push the corresponding provenance to GitHub.

---

### Task 5: Held-out causal capability gate

**Files:**
- Create: `source/scripts/eval_r17_causal_law_gate.py`
- Create: `results/r1_7_causal_law_dev_control.json`
- Create: `results/r1_7_causal_law_dev_candidate.json`
- Create: `results/r1_7_causal_law_gate_decision.json`

**Interfaces:**
- Compares frozen R1.6 EffectProgress parent against R1.7 CausalLaws on preregistered FIGG-17 dev indices.

- [ ] **Step 1: Preregister exact dev indices and acceptance rule**

Acceptance requires candidate to improve aggregate completion or action-efficiency on causal families, improve causal-law identification/calibration, and not regress preservation families beyond the preregistered tolerance.

- [ ] **Step 2: Push preregistration before evaluation**

No dev run before the GitHub commit exists.

- [ ] **Step 3: Run control and candidate**

Use identical task IDs/action budgets. Store every trace.

- [ ] **Step 4: Machine-select winner**

Write a deterministic decision JSON. Do not manually select a favorable slice.

- [ ] **Step 5: Push result and persist winner/negative branch**

Whether pass or fail, push verdict and persist the candidate checkpoint/trace ZIP to Library.

---

### Task 6: Phase-A verification and handoff

**Files:**
- Create: `R1_7_PHASE_A_REALITY_REPORT.md`
- Create: `R1_7_PHASE_A_MANIFEST.json`
- Create: milestone ZIP if the phase produces an accepted capability checkpoint.

**Interfaces:**
- Produces an accepted R1.7 causal parent or a documented negative result that leaves R1.6 EffectProgress as the parent for Phase B.

- [ ] **Step 1: Run focused R1.7 + parent regression tests**

Run all new R1.7 tests and the R1.6 model/checkpoint/benchmark integrity tests needed to prove parent preservation.

- [ ] **Step 2: Audit parameter count and hashes**

Record all candidate/parent hashes and effective parameter counts.

- [ ] **Step 3: Write Reality Report**

Separate capability evidence, offline metrics, negative results, and unproven claims. Explicitly state that no result proves AGI.

- [ ] **Step 4: Push final Phase-A report/manifest**

Push to `main` before packaging.

- [ ] **Step 5: Create, verify, expose, and persist delivery ZIP**

Create a full Phase-A ZIP, run `unzip -t`, compute SHA-256, link it in chat, and upload it to Library (split into safe volumes if necessary).
