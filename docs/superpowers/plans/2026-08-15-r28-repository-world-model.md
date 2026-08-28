# R2.8 Repository World Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a zero-parameter repository world model and epistemic active-debugging router that makes coding actions depend on repository evidence rather than workflow stage alone.

**Architecture:** A language-agnostic graph represents repository topology and edit blast radius. A normalized hypothesis ledger plus Bayesian expected-information-gain probes selects among R2.7-safe action kinds, with deterministic adversarial cases ensuring identical loop states can require different actions.

**Tech Stack:** Python 3.11, stdlib dataclasses/math/collections, pytest, existing R2.7 runtime.

## Global Constraints

- Parent neural parameters: 79,401,400.
- New R2.8 neural parameters: exactly 0.
- No language ID or task-type ID may be consumed by R2.8 world-model/planner APIs.
- R2.7 safety legality remains authoritative.
- External coding/AGI claims remain forbidden in Phase A.
- Every production behavior is introduced by a failing test first.

---

### Task 1: Repository world graph

**Files:**
- Create: `cogcoder/r28_repo_world.py`
- Test: `tests/test_r28_repo_world.py`

**Interfaces:**
- Produces: `RepoNode`, `RepoEdge`, `RepoWorldGraph.add_node`, `add_edge`, `neighbors`, `impact_closure`, `edit_risk`.

- [ ] Write tests proving reverse dependency closure includes transitive dependents and tests while excluding unrelated nodes.
- [ ] Run `pytest -q tests/test_r28_repo_world.py` and verify RED because module is missing.
- [ ] Implement immutable node/edge records, indexed adjacency/reverse-adjacency, bounded traversal, and normalized edit risk `len(impact_closure)/len(nodes)`.
- [ ] Re-run the test and verify GREEN.

### Task 2: Epistemic hypothesis ledger and information gain

**Files:**
- Create: `cogcoder/r28_epistemic_debugger.py`
- Test: `tests/test_r28_epistemic_debugger.py`

**Interfaces:**
- Consumes: `RepoWorldGraph`.
- Produces: `DebugHypothesis`, `HypothesisLedger`, `Evidence`, `EpistemicProbe`, `ActiveDebugger.expected_information_gain`, `rank_probes`.

- [ ] Write tests proving evidence renormalizes posterior probabilities and a discriminative probe has greater expected information gain than a non-discriminative probe.
- [ ] Run the focused test and verify RED.
- [ ] Implement normalized probability bookkeeping and Shannon-entropy expected information gain for binary probes.
- [ ] Add utility scoring: base controller score + information gain + posterior target coverage + action progress bonus - cost - regression risk.
- [ ] Re-run focused tests and verify GREEN.

### Task 3: Integrate epistemic routing with R2.7 safety

**Files:**
- Create: `cogcoder/r28_codeworld_runtime.py`
- Test: `tests/test_r28_runtime.py`

**Interfaces:**
- Consumes: `CodingLoopState`, `ActionProposal`, `legal_action_kinds`, `RepoWorldGraph`, `HypothesisLedger`, `EpistemicProbe`.
- Produces: `EpistemicActionDecision`, `choose_epistemic_action`.

- [ ] Write a test with identical `CodingLoopState` and identical base R2.7 proposal scores where diffuse evidence selects `reproduce_failure` but concentrated evidence selects `read_context`.
- [ ] Write a test proving illegal `finish` remains blocked even if it has the largest epistemic/base score.
- [ ] Run focused tests and verify RED.
- [ ] Implement safe candidate filtering and epistemic utility routing.
- [ ] Re-run focused tests and verify GREEN.

### Task 4: Locked adversarial Phase-A protocol

**Files:**
- Create: `benchmarks/codeworld/r28_epistemic_cases.py`
- Create: `research/R2_8_PRE_DEV_LOCK.json`
- Create: `scripts/measure_r28_epistemic_routing.py`
- Test: `tests/test_r28_protocol.py`

**Interfaces:**
- Produces: deterministic cases, `evaluate_cases()`, JSON aggregate metrics.

- [ ] Write tests requiring at least four cases sharing workflow states but differing in optimal action, plus node-renaming invariance.
- [ ] Run focused tests and verify RED.
- [ ] Implement deterministic cases and evaluator without language/task identifiers.
- [ ] Lock thresholds: candidate exact action accuracy 1.0, rename invariance 1.0, and zero neural parameters.
- [ ] Run focused tests and measure script; verify GREEN and write `research/R2_8_PHASE_A_RESULT.json`.

### Task 5: CI, delivery and full verification

**Files:**
- Create: `.github/workflows/r28-world-model.yml`
- Create: `archive/root-history/historical_r_series/R2_8_DELIVERY.md`
- Create: `archive/root-history/historical_r_series/R2_8_RELEASE_MANIFEST.json`
- Modify: `README.md` only to add a research-status note without claiming external coding performance.

**Interfaces:**
- CI runs all R2.8 tests, the measure script, validates zero parameter growth, and archives a source snapshot.

- [ ] Add CI using standalone Python commands only; no inline heredoc verifier.
- [ ] Run all R2.7 + R2.8 focused tests locally.
- [ ] Run `python scripts/measure_r28_epistemic_routing.py` and inspect the result JSON.
- [ ] Verify candidate effective parameters remain exactly 79,401,400.
- [ ] Commit/push to `main`, then require GitHub R2.7 baseline CI and R2.8 CI to complete successfully before claiming completion.
- [ ] Build a complete ZIP containing source, tests/docs/research outputs, R2.7 parent checkpoint, and milestone manifest; integrity-test it and persist it to ChatGPT Library.
