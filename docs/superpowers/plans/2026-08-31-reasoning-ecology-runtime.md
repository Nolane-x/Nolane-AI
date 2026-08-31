# C9 Reasoning Ecology Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a replayable, budget-conserving, stale-safe Reasoning Episode runtime that proves how one C8 epistemic frontier evolves into the next without gaining execution, promotion, Assurance, D, Transfer/Meta, Cognitive Library or Neural authority.

**Architecture:** Add one immutable temporal-composition module, `reasoning_episode.py`, over existing `ReasoningFrontier`, `ReasoningActionProposal`, `MetareasoningBudget` and `ReasoningControlDecision`. All spent budget, frontier deltas, status and snapshot identity are derived from a replayable transition chain rather than caller-owned mutable counters.

**Tech Stack:** Python 3.11/3.13, stdlib dataclasses/enums/math/typing, existing `nolane.core.canonical_digest`, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-31-reasoning-ecology-runtime-design.md`

## Global Constraints

- `external.reasoning_invention` advances from canonical revision `2` / component version `0.0.2` to revision `3` / `0.0.3`.
- Existing C1/C7/C8 schema identifiers remain unchanged; C9 introduces only `reasoning-episode-v1`.
- The episode runtime never invokes tools, models, E Acting, experiments or reviewers.
- The episode runtime never mutates Cognitive Library, Capability Acquisition, Transfer/Meta, Assurance, D Goal/Design or Neural state.
- No hidden weighted scalar is introduced for Pareto action selection.
- Critical decision-overturning unknowns remain governed by C8 abstention semantics; budget exhaustion is never acceptance.
- Serialized restoration must replay the exact transition prefix and reject forged derived state.
- Nolane World is design provenance only and is never imported by Nolane AI runtime code.

---

## File Structure

### New production file

`nolane/external_core/reasoning_episode.py`

Owns only episode status, frontier-delta derivation, transition proof, immutable episode snapshots, open/advance/close operations and canonical replay.

### New tests

`tests/test_refoundation_post_epoch0_reasoning_episode.py`

Covers normative open/advance/close/replay semantics and v0.0.3 coherence.

`tests/test_refoundation_post_epoch0_reasoning_episode_adversarial.py`

Covers stale authority, budget forgery, topology forgery, cross-context drift, duplicate consumption and authority-backdoor rejection.

### Existing files modified during revision cutover

- `nolane/external_core/reasoning_invention.py`
- `nolane/external_core/reasoning_evaluation.py`
- `nolane/external_core/reasoning_frontier.py`
- `nolane/external_core/reasoning_metacontrol.py`
- `nolane/external_core/reasoning_review.py`
- `nolane/external_core/reasoning_meta_learning.py`
- `nolane/metadata/component_versions.py`
- `nolane/metadata/_component_specs.py`
- `nolane/metadata/implementation_status.py`
- `tests/test_refoundation_component_versions.py`
- `tests/test_refoundation_post_epoch0_reasoning_invention_metadata.py`
- `tests/test_refoundation_post_epoch0_reasoning_metacontrol.py`
- `CURRENT/REASONING_INVENTION_C_LAYER.md`
- `CURRENT/EXTERNAL_CORE.md`

---

### Task 1: Establish C9 RED contracts

**Files:**
- Create: `tests/test_refoundation_post_epoch0_reasoning_episode.py`
- Create: `tests/test_refoundation_post_epoch0_reasoning_episode_adversarial.py`

**Interfaces:**
- Consumes: existing `ReasoningFrontier`, `ReasoningActionProposal`, `MetareasoningBudget`, `ReasoningControlDecision`, `plan_next_reasoning_actions`.
- Produces: executable specification for `ReasoningEpisodeStatus`, `ReasoningFrontierDelta`, `ReasoningFrontierTransition`, `ReasoningEpisode`, `open_reasoning_episode`, `advance_reasoning_episode`, `close_reasoning_episode`.

- [ ] **Step 1: Write the normative failing tests**

Use existing C8 objects to assert the intended C9 API:

```python
from nolane.external_core.reasoning_episode import (
    ReasoningEpisode,
    ReasoningEpisodeStatus,
    advance_reasoning_episode,
    close_reasoning_episode,
    open_reasoning_episode,
)


def test_episode_open_derives_exact_current_budget():
    episode = open_reasoning_episode(
        root_frontier,
        action_limit=3,
        cost_limit=5.0,
        minimum_actionable_gain=0.2,
    )
    assert episode.status is ReasoningEpisodeStatus.ACTIVE
    assert episode.current_frontier == root_frontier
    assert episode.spent_actions == 0
    assert episode.spent_cost == 0.0
    assert episode.current_budget.frontier_id == root_frontier.frontier_id
    assert episode.current_budget.remaining_actions == 3
    assert episode.current_budget.remaining_cost == 5.0
```

Also specify one valid transition, exact unknown/rival/assumption delta, exact-budget close, overrun terminalization, canonical round-trip and version `0.0.3`.

- [ ] **Step 2: Write adversarial failing tests**

Require rejection of:

```python
# stale decision after frontier advance
with pytest.raises(ValueError, match="stale|frontier|budget"):
    advance_reasoning_episode(advanced, old_decision, old_action, next_frontier, 1.0, ("evidence:x",))

# same action authority twice
with pytest.raises(ValueError, match="consumed|reuse|action"):
    advance_reasoning_episode(advanced, reused_control, old_action, later_frontier, 1.0, ("evidence:y",))

# D-owned hard constraint drift
with pytest.raises(ValueError, match="constraint|context|continuity"):
    advance_reasoning_episode(episode, decision, action, drifted_frontier, 1.0, ("evidence:z",))
```

Also forge serialized generation, current frontier, status, transition IDs, snapshot ID and duplicate control IDs. Scan `reasoning_episode.py` for forbidden execution/promotion authority surfaces.

- [ ] **Step 3: Commit RED tests before production code**

Commit only the new test files with message:

```text
test: specify C9 reasoning episode runtime
```

- [ ] **Step 4: Run hosted RED proof**

Require `tests/test_refoundation_post_epoch0_reasoning_episode*.py` to fail because `reasoning_episode` and the v0.0.3 cutover do not exist. Inspect the exact Python 3.11 failure and retain its run/head IDs before writing production code.

---

### Task 2: Implement immutable frontier transition proofs

**Files:**
- Create: `nolane/external_core/reasoning_episode.py`
- Test: `tests/test_refoundation_post_epoch0_reasoning_episode.py`
- Test: `tests/test_refoundation_post_epoch0_reasoning_episode_adversarial.py`

**Interfaces:**
- Consumes:
  - `ReasoningFrontier.frontier_id`
  - `ReasoningFrontier.unknowns`
  - `ReasoningFrontier.rivals`
  - `ReasoningFrontier.assumption_ids`
  - `ReasoningActionProposal.action_id`
  - `ReasoningControlDecision.decision_id`
- Produces:
  - `ReasoningFrontierDelta`
  - `derive_frontier_delta(previous, next, evidence_ids)`
  - `ReasoningFrontierTransition`

- [ ] **Step 1: Add strict local validation helpers**

Implement non-empty IDs, canonical distinct/sorted ID sets, finite numbers, positive finite numbers, positive integers and content identity using `canonical_digest`. Explicitly reject bool as numeric input.

- [ ] **Step 2: Implement `ReasoningFrontierDelta`**

Exact fields:

```python
@dataclass(frozen=True, slots=True)
class ReasoningFrontierDelta:
    previous_frontier_id: str
    next_frontier_id: str
    resolved_unknown_ids: tuple[str, ...]
    introduced_unknown_ids: tuple[str, ...]
    retired_hypothesis_ids: tuple[str, ...]
    introduced_hypothesis_ids: tuple[str, ...]
    revised_hypothesis_ids: tuple[str, ...]
    retired_assumption_ids: tuple[str, ...]
    introduced_assumption_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    delta_id: str = field(init=False)
```

`derive_frontier_delta` computes set changes itself. Hypothesis revision means the same `hypothesis_id` exists on both frontiers with different `rival_id`.

- [ ] **Step 3: Enforce successor continuity**

Create an internal verifier requiring equality of:

```text
reasoning_receipt_id
objective_id
cognitive_library_digest
hard_constraint_ids
branch_budget
```

Reject identical frontier IDs: an advance must produce a new semantic frontier.

- [ ] **Step 4: Implement `ReasoningFrontierTransition`**

Exact fields:

```python
@dataclass(frozen=True, slots=True)
class ReasoningFrontierTransition:
    episode_key: str
    generation: int
    previous_frontier_id: str
    next_frontier: ReasoningFrontier
    control_decision: ReasoningControlDecision
    selected_action: ReasoningActionProposal
    delta: ReasoningFrontierDelta
    observed_cost: float
    budget_overrun: bool
    transition_id: str = field(init=False)
```

`budget_overrun` is validated against the pre-transition remaining cost by episode replay/advancement logic; direct construction cannot be accepted as episode authority without that outer verification.

- [ ] **Step 5: Run focused delta/continuity tests and commit**

Expected: transition/delta-focused tests GREEN while episode/replay/version tests may remain RED.

Commit:

```text
feat: add C9 frontier transition proofs
```

---

### Task 3: Implement budget-conserving ReasoningEpisode lifecycle

**Files:**
- Modify: `nolane/external_core/reasoning_episode.py`
- Test: both C9 test files

**Interfaces:**
- Consumes: Task 2 delta/transition types and existing C8 metacontrol types.
- Produces:
  - `ReasoningEpisodeStatus`
  - `ReasoningEpisode`
  - `open_reasoning_episode`
  - `advance_reasoning_episode`
  - `close_reasoning_episode`

- [ ] **Step 1: Implement status enum**

```python
class ReasoningEpisodeStatus(str, Enum):
    ACTIVE = "active"
    HALTED_NO_FURTHER_VALUE = "halted_no_further_value"
    ABSTAINED_UNRESOLVED = "abstained_unresolved"
    ABSTAINED_BUDGET_OVERRUN = "abstained_budget_overrun"
```

- [ ] **Step 2: Implement immutable `ReasoningEpisode`**

Store root/current frontier, initial action/cost/gain budget, transitions, terminal decision, status, stable `episode_key`, derived `snapshot_id`.

Derived properties:

```python
@property
def spent_actions(self) -> int:
    return len(self.transitions)

@property
def spent_cost(self) -> float:
    return sum(row.observed_cost for row in self.transitions)

@property
def current_budget(self) -> MetareasoningBudget:
    return MetareasoningBudget(
        frontier_id=self.current_frontier.frontier_id,
        remaining_actions=max(self.action_limit - self.spent_actions, 0),
        remaining_cost=max(self.cost_limit - self.spent_cost, 0.0),
        minimum_actionable_gain=self.minimum_actionable_gain,
    )
```

- [ ] **Step 3: Implement open**

`open_reasoning_episode` validates initial limits and creates generation zero with no terminal decision.

- [ ] **Step 4: Implement advance authorization**

Before creating a transition, require:

```python
control_decision.disposition is ControlDisposition.CONTINUE
control_decision.frontier_id == episode.current_frontier.frontier_id
control_decision.budget_id == episode.current_budget.budget_id
selected_action.frontier_id == episode.current_frontier.frontier_id
selected_action.action_id in control_decision.pareto_action_ids
selected_action.estimated_cost <= episode.current_budget.remaining_cost
```

Also reject reused decision/action IDs and continuity drift.

Derive delta from before/after frontiers and caller evidence IDs. Record actual observed cost. If actual cost exceeds pre-transition remaining cost, return a terminal `ABSTAINED_BUDGET_OVERRUN` episode.

- [ ] **Step 5: Implement explicit close**

`close_reasoning_episode` accepts only current-frontier/current-budget terminal decisions. Map C8 halt/abstain exactly to the two corresponding episode states. Reject `CONTINUE`, already-terminal episodes and budget-overrun relabeling.

- [ ] **Step 6: Run focused lifecycle tests and commit**

Commit:

```text
feat: add C9 reasoning episode lifecycle
```

---

### Task 4: Make episode persistence replay-verifiable

**Files:**
- Modify: `nolane/external_core/reasoning_episode.py`
- Test: both C9 test files

**Interfaces:**
- Consumes: Task 3 live lifecycle.
- Produces: canonical `ReasoningEpisode.to_state()` / `ReasoningEpisode.from_state()`.

- [ ] **Step 1: Serialize only canonical explicit state**

State contains schema version, episode/snapshot identities, root/current frontier states, initial budget parameters, transition states, optional terminal decision state and status.

- [ ] **Step 2: Replay from root instead of trusting derived fields**

`from_state` must reconstruct generation zero, then replay each serialized transition through the same internal verifier used by live advancement. For each row, compare reconstructed transition ID, derived delta and overrun flag with serialized content.

- [ ] **Step 3: Verify final claimed snapshot**

After replay and optional close, require exact equality of:

```text
current_frontier
status
terminal_control_decision
episode_key
snapshot_id
full canonical to_state()
```

Reject extra/non-canonical state via final `row.to_state() == dict(state)` equality.

- [ ] **Step 4: Run forged-state/adversarial tests and commit**

Commit:

```text
feat: make C9 episodes replay-verifiable
```

---

### Task 5: Cut Reasoning/Invention revision to v0.0.3

**Files:**
- Modify: `nolane/external_core/reasoning_invention.py`
- Modify: `nolane/external_core/reasoning_evaluation.py`
- Modify: `nolane/external_core/reasoning_frontier.py`
- Modify: `nolane/external_core/reasoning_metacontrol.py`
- Modify: `nolane/external_core/reasoning_review.py`
- Modify: `nolane/external_core/reasoning_meta_learning.py`
- Modify: `nolane/metadata/component_versions.py`
- Modify: `tests/test_refoundation_component_versions.py`
- Modify: `tests/test_refoundation_post_epoch0_reasoning_invention_metadata.py`
- Modify: `tests/test_refoundation_post_epoch0_reasoning_metacontrol.py`

**Interfaces:**
- Produces one coherent Reasoning/Invention component revision `0.0.3` with unchanged existing wire schemas.

- [ ] **Step 1: Advance runtime-family constants**

Set `COMPONENT_VERSION = "0.0.3"` in every Reasoning/Invention-family module, including C9.

- [ ] **Step 2: Advance canonical revision map only for Reasoning/Invention**

Change:

```python
"external.reasoning_invention": 2,
```

to:

```python
"external.reasoning_invention": 3,
```

Preserve the concurrently accepted E value:

```python
"external.execution.control": 7,
```

and every other component's current revision.

- [ ] **Step 3: Update version assertions**

Require `0.0.3` / revision `3` in metadata and C8/C9 coherence tests. Continue asserting unchanged schema identifiers.

- [ ] **Step 4: Run C8+C9+component-version tests and commit**

Commit:

```text
feat: cut Reasoning Invention v0.0.3
```

---

### Task 6: Update canonical architecture/status documentation

**Files:**
- Modify: `nolane/metadata/_component_specs.py`
- Modify: `nolane/metadata/implementation_status.py`
- Modify: `CURRENT/REASONING_INVENTION_C_LAYER.md`
- Modify: `CURRENT/EXTERNAL_CORE.md`

**Interfaces:**
- Produces canonical documentation matching the v0.0.3 runtime and authority boundary.

- [ ] **Step 1: Extend component description**

Describe Reasoning/Invention as including replayable, budget-conserving episode/frontier evolution while remaining evidence-only and authority-bounded.

- [ ] **Step 2: Add C9 section to CURRENT**

Document episode key versus snapshot ID, stale `(frontier_id, budget_id)` fencing, transition evidence, replay integrity, exact exhaustion versus overrun semantics, and no-execution/no-promotion authority.

- [ ] **Step 3: Update External Core summary**

Move Reasoning/Invention from v0.0.2 to v0.0.3 and name C9 temporal/replay closure.

- [ ] **Step 4: Run implementation-status/metadata tests and commit**

Commit:

```text
docs: record C9 reasoning ecology runtime
```

---

### Task 7: Exact-head verification, latest-main resync and PR record

**Files:**
- No production behavior additions unless a verified C-caused regression is found.
- Update PR #236 body only after final evidence is terminal.

**Interfaces:**
- Produces integration evidence for the exact final PR synthetic merge.

- [ ] **Step 1: Verify focused GREEN on hosted Python 3.11 and 3.13**

Require C9 normative/adversarial tests plus all existing C8 tests to pass.

- [ ] **Step 2: Verify full Refoundation matrix**

Require on exact synthetic merge:

```text
python -m compileall -q cogcoder/organization cogcoder/refoundation nolane
python -m nolane.ai.materialize --check
python -m nolane.repository.audit --check
python -m pytest -q tests/test_refoundation_*.py
python -m pytest -q tests/test_truth_knowledge_*.py
full downstream organization/campaign/execution regression command
Neural R2.3 verification
```

on Python 3.11 and 3.13.

- [ ] **Step 3: Classify broad workflow results**

Inspect R1.9, R2.0i, Memory, E Acting and current R2.x gates. Do not modify C to satisfy frozen historical source/release-lock workflows unless C actually changes their protected bytes or behavior.

- [ ] **Step 4: Race-guard latest `main`**

Fetch `main` immediately before closure. If it advanced, compare exact files, resolve only genuine shared authority conflicts, create a history-preserving two-parent merge and rerun the exact synthetic-merge gates.

- [ ] **Step 5: Verify merge hygiene**

Require:

```text
behind_by == 0
PR mergeable == true
PR delta contains only intended C/metadata/docs/tests relative to current main
no unresolved C review thread
```

- [ ] **Step 6: Update PR acceptance record**

Record final head SHA, base SHA, synthetic merge SHA, RED evidence, GREEN counts, broad-gate classification and C9 authority invariants. Do not merge the PR unless explicitly requested by the user.
