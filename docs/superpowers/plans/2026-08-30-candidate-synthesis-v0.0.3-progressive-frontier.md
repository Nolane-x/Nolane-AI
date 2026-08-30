# Candidate Synthesis v0.0.3 Progressive Frontier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic progressive multi-depth synthesis mode that searches complete ordered-permutation frontiers from depth 2 through source-pool size, returns only from the shallowest fully searched novel frontier, and preserves all Candidate Synthesis authority/serialization boundaries.

**Architecture:** Extend the existing stateless `CandidateSynthesisEngine` instead of introducing a new subsystem. Reuse `_resolve_sources`, `_compose_sources`, `_installed_abstraction`, `_return`, `_abstain`, and the existing structural score. The new mode canonicalizes its source pool like v0.0.2 bounded search, enumerates `permutations(sources, depth)` without replacement, accounts every attempted hypothesis against one global budget, and refuses to return a winner from a partially searched frontier.

**Tech Stack:** Python 3.11/3.13, stdlib `itertools.permutations`, pytest, canonical digest/state contracts, GitHub Actions Refoundation Epoch 0 workflow.

**Spec:** `docs/superpowers/specs/2026-08-30-candidate-synthesis-v0.0.3-progressive-frontier-design.md`

## Global Constraints

- `COMPONENT_VERSION` becomes exactly `0.0.3`.
- `SCHEMA_VERSION` remains exactly `candidate-synthesis-v1`.
- Add exactly one mode: `SynthesisMode.PROGRESSIVE_MULTI_DEPTH_SEARCH = "progressive_multi_depth_search"`.
- Existing `LEARNED_ABSTRACTION_COMPOSITION` and `BOUNDED_LEARNED_ABSTRACTION_SEARCH` semantics remain unchanged.
- Progressive source pools are unordered/canonical; hypothesis sequence order is semantic.
- Hypotheses use ordered permutations without replacement for depths `2..len(source_pool)`.
- Global `generation_budget` counts attempted hypotheses before filtering/deduplication.
- A partial frontier can never return a winner and can never authorize descent to a deeper frontier.
- Budget exhaustion before current-frontier completion returns `generation_budget_exhausted`.
- Full exhaustion of all depth frontiers with no novel candidate returns `no_novel_candidate`.
- Generated intermediates never enter Cognitive Library or same-call vocabulary.
- Candidate Synthesis accepts discovery evidence only and gains no admit/probation/Assurance/promotion/quarantine/Neural authority.
- Final implementation PR must be non-draft and exact-head CI must pass on Python 3.11 and 3.13 before merge.

---

### Task 1: Lock v0.0.3 RED contracts

**Files:**
- Create: `tests/test_refoundation_post_epoch0_candidate_synthesis_progressive_frontier.py`
- Modify: `tests/test_refoundation_post_epoch0_candidate_synthesis.py`
- Modify: `tests/test_refoundation_component_versions.py`

**Interfaces:**
- Consumes: existing `CandidateSynthesisEngine`, `SynthesisRequest`, `SynthesisReceipt`, `SynthesisMode`, `CapabilityCandidate`, `CognitiveLibrary`, `LearnedAbstraction`.
- Produces: failing behavioral/version contracts for `PROGRESSIVE_MULTI_DEPTH_SEARCH`, v0.0.3 metadata, and unchanged legacy-mode behavior.

- [ ] **Step 1: Advance only test expectations for component revision/version**

Change the existing Candidate Synthesis declaration test to require `0.0.3` while keeping state schema v1:

```python
def test_candidate_synthesis_is_declared_as_native_v003_component() -> None:
    assert importlib.util.find_spec(CANONICAL_MODULE) is not None
    manifests = {row.component_id: row for row in build_component_manifests()}
    manifest = manifests[COMPONENT_ID]
    assert str(manifest.version) == "0.0.3"
    assert manifest.layer == "external_core"
    assert manifest.state_schema == "candidate-synthesis-v1"

    record = build_component_implementation_ledger()[COMPONENT_ID]
    assert record.status is ImplementationStatus.CANONICAL_NATIVE
    assert record.component_version == "0.0.3"
    assert record.canonical_module == CANONICAL_MODULE
    assert record.legacy_sources == ()
```

Set `ACCEPTED_COMPONENT_REVISIONS["external.candidate_synthesis"] = 3` in `tests/test_refoundation_component_versions.py`.

- [ ] **Step 2: Create progressive-frontier fixtures and oracle helpers**

Use three canonical unary sources with distinct structure/support:

```python
def _simple(op: str, task_id: str) -> LearnedAbstraction:
    template = Unary(op, TemplateParam(0))
    return make_abstraction(
        template,
        parameter_count=1,
        support_task_ids=(task_id,),
        raw_occurrence_cost=template.cost,
        rewritten_cost=template.cost,
    )


def _complex(task_id: str) -> LearnedAbstraction:
    template = Binary("add", TemplateParam(0), TemplateParam(0))
    return make_abstraction(
        template,
        parameter_count=1,
        support_task_ids=(task_id,),
        raw_occurrence_cost=template.cost,
        rewritten_cost=template.cost,
    )
```

Build a helper request with `getattr(SynthesisMode, "PROGRESSIVE_MULTI_DEPTH_SEARCH")`, discovery evidence, and caller-provided budget. Build independent composition oracles by invoking only the already-existing `LEARNED_ABSTRACTION_COMPOSITION` mode for an exact ordered source tuple.

- [ ] **Step 3: Lock pool canonicalization and v1 serialization**

Add tests equivalent to:

```python
def test_progressive_pool_order_is_canonical_and_request_round_trips() -> None:
    library, sources = _search_library()
    ids = tuple(row.abstraction_id for row in sources)
    first = _progressive_request(ids, budget=6)
    second = _progressive_request(tuple(reversed(ids)), budget=6)
    assert first.source_item_ids == tuple(sorted(ids))
    assert second == first
    assert SynthesisRequest.from_state(first.to_state()) == first
    assert first.to_state()["schema_version"] == "candidate-synthesis-v1"
```

- [ ] **Step 4: Lock complete-frontier requirement**

For three sources the depth-2 frontier size is `P(3,2)=6`. With budget 5, progressive mode must not return a partial winner:

```python
def test_partial_depth_two_frontier_abstains_even_after_observing_novel_candidates() -> None:
    library, sources = _search_library()
    result = CandidateSynthesisEngine(library).synthesize(
        _progressive_request(tuple(row.abstraction_id for row in sources), budget=5)
    )
    assert result.candidate is None
    assert result.receipt.candidates_considered == 5
    assert result.receipt.abstention_reason == "generation_budget_exhausted"
```

With budget 6 and ordinary novel pair results, the engine must complete depth 2, rank that full frontier, and return the same winner as the independent pairwise oracle.

- [ ] **Step 5: Lock actual depth-3 capability**

Construct all six depth-2 candidates using the existing composition oracle, install those generated abstractions beside the original three sources, then run progressive mode with budget 12 (`6` depth-2 + `6` depth-3 hypotheses). Assert:

```python
assert result.candidate is not None
assert result.receipt.candidates_considered == 12
payload = result.candidate.payload()
assert isinstance(payload, LearnedAbstraction)
assert len(payload.support_task_ids) == 3
assert "call" not in repr(payload.template.to_data())
assert populated.digest == library_before
```

Derive the expected depth-3 winner independently from all `itertools.permutations(ordered_sources, 3)` through composition mode, then apply the existing structural score tuple `(template.cost, -len(support_task_ids), candidate_id)`.

- [ ] **Step 6: Lock no descent through an incomplete shallow frontier**

With all pair results installed but budget `5`, assert `generation_budget_exhausted`, considered `5`, and no result. With budget `6`, depth 2 is complete but there is no remaining budget for depth 3; because the next required frontier cannot even begin, assert `generation_budget_exhausted`, considered `6`, and no result. With budget `11`, depth 3 is partial; assert no result and considered `11`.

- [ ] **Step 7: Lock full-space exhaustion semantics**

Install all depth-2 and depth-3 candidates for a three-source pool. With budget at least 12, assert:

```python
assert result.candidate is None
assert result.receipt.candidates_considered == 12
assert result.receipt.abstention_reason == "no_novel_candidate"
```

- [ ] **Step 8: Lock authority, evidence, receipt, and no-intermediate invariants**

Add focused tests that:
- reject `INDEPENDENT_CHALLENGE` and `FINAL_ASSURANCE` evidence at request construction;
- compare library digest and governor digest before/after progressive synthesis;
- prove `governor.records() == ()` until an explicit `admit` call;
- prove explicit admit yields `CapabilityState.CANDIDATE` only;
- round-trip `SynthesisReceipt` and reject a tampered `candidates_considered` or `synthesis_id`;
- assert no generated pair abstraction was inserted into the original library when a depth-3 candidate is returned.

- [ ] **Step 9: Run RED on both supported Python versions**

Run the focused suite plus component-version tests under Python 3.11 and 3.13:

```bash
python -m pytest -q \
  tests/test_refoundation_post_epoch0_candidate_synthesis.py \
  tests/test_refoundation_post_epoch0_candidate_synthesis_bounded_search.py \
  tests/test_refoundation_post_epoch0_candidate_synthesis_progressive_frontier.py \
  tests/test_refoundation_component_versions.py
```

Expected RED reason: missing `SynthesisMode.PROGRESSIVE_MULTI_DEPTH_SEARCH` and component still reporting `0.0.2`; existing v0.0.1/v0.0.2 tests should otherwise remain green. A setup, collection, fixture, or oracle bug does not count as RED evidence and must be corrected before production changes.

- [ ] **Step 10: Commit RED tests only**

```bash
git add tests/test_refoundation_post_epoch0_candidate_synthesis.py \
        tests/test_refoundation_post_epoch0_candidate_synthesis_progressive_frontier.py \
        tests/test_refoundation_component_versions.py
git commit -m "test: lock progressive candidate synthesis frontier"
```

---

### Task 2: Implement protocol surface and canonical source semantics

**Files:**
- Modify: `nolane/external_core/candidate_synthesis.py`
- Modify: `nolane/metadata/component_versions.py`

**Interfaces:**
- Consumes: existing request/receipt schema v1 and `_source_ids_for_mode`.
- Produces: `SynthesisMode.PROGRESSIVE_MULTI_DEPTH_SEARCH`, component revision 3, canonical progressive source-pool handling.

- [ ] **Step 1: Add mode and version only**

```python
COMPONENT_VERSION = "0.0.3"
SCHEMA_VERSION = "candidate-synthesis-v1"

class SynthesisMode(str, Enum):
    LEARNED_ABSTRACTION_COMPOSITION = "learned_abstraction_composition"
    BOUNDED_LEARNED_ABSTRACTION_SEARCH = "bounded_learned_abstraction_search"
    PROGRESSIVE_MULTI_DEPTH_SEARCH = "progressive_multi_depth_search"
```

- [ ] **Step 2: Canonicalize progressive source pools with the existing bounded-search rule**

Change `_source_ids_for_mode` so both search modes sort source IDs, while composition preserves caller sequence:

```python
if mode in (
    SynthesisMode.BOUNDED_LEARNED_ABSTRACTION_SEARCH,
    SynthesisMode.PROGRESSIVE_MULTI_DEPTH_SEARCH,
):
    return tuple(sorted(rows))
```

- [ ] **Step 3: Advance metadata revision**

Change only:

```python
"external.candidate_synthesis": 3,
```

in `nolane/metadata/component_versions.py`.

- [ ] **Step 4: Run protocol/version subset**

Run tests for version, enum availability, canonical pool order, request round-trip, and legacy-mode order semantics. Expected: version/canonicalization tests pass; progressive engine behavior tests remain RED because dispatch/search implementation is still absent.

- [ ] **Step 5: Commit protocol surface**

```bash
git add nolane/external_core/candidate_synthesis.py nolane/metadata/component_versions.py
git commit -m "feat: declare progressive candidate synthesis mode"
```

---

### Task 3: Implement progressive frontier engine with hard accounting

**Files:**
- Modify: `nolane/external_core/candidate_synthesis.py`
- Test: `tests/test_refoundation_post_epoch0_candidate_synthesis_progressive_frontier.py`

**Interfaces:**
- Consumes: `_resolve_sources`, `_compose_sources`, `_installed_abstraction`, `_abstain`, `_return`, `CapabilityCandidate.for_learned_abstraction`.
- Produces: `_synthesize_progressive_search(before_digest, request, sources) -> SynthesisResult` and dispatch from `synthesize`.

- [ ] **Step 1: Factor one structural score helper without changing v0.0.2 behavior**

Use one deterministic helper for both search modes:

```python
def _candidate_score(candidate: CapabilityCandidate) -> tuple[int, int, str]:
    payload = candidate.payload()
    if not isinstance(payload, LearnedAbstraction):
        raise TypeError("candidate synthesis ranking requires learned abstraction payload")
    return (
        payload.template.cost,
        -len(payload.support_task_ids),
        candidate.candidate_id,
    )
```

Update bounded pair search to use this helper and verify its existing tests stay identical.

- [ ] **Step 2: Implement progressive depth traversal**

The core shape must be equivalent to:

```python
def _synthesize_progressive_search(
    self,
    before_digest: str,
    request: SynthesisRequest,
    sources: Sequence[LearnedAbstraction],
) -> SynthesisResult:
    source_ids = set(request.source_item_ids)
    seen_candidate_ids: set[str] = set()
    considered = 0

    for depth in range(2, len(sources) + 1):
        frontier = tuple(permutations(sources, depth))
        frontier_size = len(frontier)
        remaining = request.generation_budget - considered
        if remaining < frontier_size:
            for hypothesis in frontier[:remaining]:
                considered += 1
                generated = self._compose_sources(hypothesis)
                # perform the same collision/install/dedup checks so accounting
                # and fail-closed identity behavior apply to attempted hypotheses;
                # do not allow any observed candidate to escape.
                if generated.abstraction_id in source_ids:
                    continue
                if self._installed_abstraction(generated) is not None:
                    continue
                candidate = CapabilityCandidate.for_learned_abstraction(generated)
                seen_candidate_ids.add(candidate.candidate_id)
            return self._abstain(
                before_digest,
                request,
                candidates_considered=considered,
                reason="generation_budget_exhausted",
            )

        frontier_candidates: dict[str, CapabilityCandidate] = {}
        for hypothesis in frontier:
            considered += 1
            generated = self._compose_sources(hypothesis)
            if generated.abstraction_id in source_ids:
                continue
            if self._installed_abstraction(generated) is not None:
                continue
            candidate = CapabilityCandidate.for_learned_abstraction(generated)
            if candidate.candidate_id in seen_candidate_ids:
                continue
            seen_candidate_ids.add(candidate.candidate_id)
            frontier_candidates[candidate.candidate_id] = candidate

        if frontier_candidates:
            best = min(frontier_candidates.values(), key=_candidate_score)
            return self._return(
                before_digest,
                SynthesisResult(
                    candidate=best,
                    receipt=_receipt(
                        request,
                        candidates_considered=considered,
                        candidate=best,
                    ),
                ),
            )

    return self._abstain(
        before_digest,
        request,
        candidates_considered=considered,
        reason="no_novel_candidate",
    )
```

Implementation may avoid materializing the tuple for efficiency, but it must preserve the same deterministic semantics. If avoiding tuple materialization, compute frontier size with `math.perm(len(sources), depth)` and iterate the exact same `permutations` order.

- [ ] **Step 3: Handle zero/edge budget without weakening the top-level invariant**

Keep the existing top-level zero-budget path as `generation_budget_exhausted`. Ensure progressive mode with exactly enough budget to complete a no-novel depth but zero remaining for a deeper required depth returns `generation_budget_exhausted`, not `no_novel_candidate`.

- [ ] **Step 4: Dispatch progressive mode**

Add after existing composition and bounded-search dispatch:

```python
if request.mode is SynthesisMode.PROGRESSIVE_MULTI_DEPTH_SEARCH:
    return self._synthesize_progressive_search(before_digest, request, sources)
```

- [ ] **Step 5: Run focused GREEN**

Run the progressive test module plus both older Candidate Synthesis modules. Expected: all Candidate Synthesis behavioral contracts pass, including unchanged v0.0.1 composition and v0.0.2 pair-search behavior.

- [ ] **Step 6: Commit engine behavior**

```bash
git add nolane/external_core/candidate_synthesis.py \
        tests/test_refoundation_post_epoch0_candidate_synthesis_progressive_frontier.py
git commit -m "feat: add progressive multi-depth synthesis frontier"
```

---

### Task 4: Harden edge cases and exact authority invariants

**Files:**
- Modify only if tests expose a real gap: `nolane/external_core/candidate_synthesis.py`
- Test: `tests/test_refoundation_post_epoch0_candidate_synthesis_progressive_frontier.py`

**Interfaces:**
- Consumes: completed progressive engine.
- Produces: explicit contracts for no source reuse, no same-call intermediate vocabulary, deterministic budget truncation, global semantic dedup, and fail-closed library collision behavior.

- [ ] **Step 1: Add a repeated-source detector test through enumeration observability**

Use a three-source pool and a budget covering all allowed frontiers. Derive the expected attempted hypothesis count as:

```python
sum(math.perm(3, depth) for depth in range(2, 4)) == 12
```

Assert full-space exhaustion considers exactly 12, not a count that would be possible only with repeated-source products.

- [ ] **Step 2: Add deterministic truncation identity test**

Run the same progressive request twice with source order reversed and a budget that truncates depth 3. Assert both abstain, both consider the same count, and both receipts have the same `synthesis_id`.

- [ ] **Step 3: Add library-collision test**

Construct or reuse the same identity-collision fixture style as existing Candidate Synthesis tests. Assert progressive search raises `ValueError("generated abstraction identity collides with different library payload")` rather than silently treating collision as installed/deduped.

- [ ] **Step 4: Run focused suite and component metadata tests**

```bash
python -m pytest -q \
  tests/test_refoundation_post_epoch0_candidate_synthesis.py \
  tests/test_refoundation_post_epoch0_candidate_synthesis_bounded_search.py \
  tests/test_refoundation_post_epoch0_candidate_synthesis_progressive_frontier.py \
  tests/test_refoundation_component_versions.py
```

Expected: all pass.

- [ ] **Step 5: Commit hardening only if new production changes were required**

If the added tests pass without production edits, commit only the new tests. If a real gap was found, commit the minimal fix with the tests that exposed it.

---

### Task 5: Document accepted v0.0.3 semantics

**Files:**
- Modify: `CURRENT/EXTERNAL_CORE.md`

**Interfaces:**
- Consumes: verified implementation semantics.
- Produces: current architectural documentation matching code and receipts.

- [ ] **Step 1: Advance Candidate Synthesis documentation to v0.0.3**

Document that v0.0.3 adds progressive multi-depth ordered-permutation frontiers without replacement, uses the shallowest fully searched frontier containing novel candidates, never returns from a partial frontier, distinguishes budget exhaustion from full no-novel exhaustion, and keeps generated intermediates outside Cognitive Library.

- [ ] **Step 2: Preserve authority wording**

The documentation must explicitly retain discovery-only evidence, no Assurance/lifecycle authority, no Cognitive Library mutation, and standalone final candidates.

- [ ] **Step 3: Run documentation-sensitive Refoundation tests if any and `git diff --check`**

```bash
git diff --check
python -m pytest -q tests/test_refoundation_component_versions.py \
  tests/test_refoundation_post_epoch0_candidate_synthesis*.py
```

- [ ] **Step 4: Commit docs**

```bash
git add CURRENT/EXTERNAL_CORE.md
git commit -m "docs: describe progressive candidate synthesis frontier"
```

---

### Task 6: Exact-head verification, PR, merge, and post-merge proof

**Files:**
- No intended production-file additions beyond Tasks 1-5.
- Temporary workflow carrier is permitted only if required by connector/runtime limitations and must be deleted before final exact-head CI.

**Interfaces:**
- Consumes: final feature head.
- Produces: canonical CI evidence, non-draft PR, expected-head merge, verified `main` tree.

- [ ] **Step 1: Inspect final diff scope**

Expected persistent changed files relative to base are limited to:

```text
CURRENT/EXTERNAL_CORE.md
docs/superpowers/specs/2026-08-30-candidate-synthesis-v0.0.3-progressive-frontier-design.md
docs/superpowers/plans/2026-08-30-candidate-synthesis-v0.0.3-progressive-frontier.md
nolane/external_core/candidate_synthesis.py
nolane/metadata/component_versions.py
tests/test_refoundation_component_versions.py
tests/test_refoundation_post_epoch0_candidate_synthesis.py
tests/test_refoundation_post_epoch0_candidate_synthesis_progressive_frontier.py
```

The existing bounded-search test file should remain unchanged unless a version-only expectation is actually present there.

- [ ] **Step 2: Run full local/runner verification on the exact feature head**

Required commands/gates:

```bash
python -m compileall -q cogcoder/organization cogcoder/refoundation nolane
python -m nolane.ai.materialize --check
python -m nolane.repository.audit --check
python -m pytest -q tests/test_refoundation_*.py
python model/neural-r2.3/scripts/verify_neural_r23.py
git diff --check
```

Also run the broad coding-AGI regression groups exactly as encoded in `.github/workflows/refoundation-epoch0-wave1.yml`.

- [ ] **Step 3: Open PR non-draft from the beginning**

Use base `main`, head `post-epoch0/candidate-synthesis-v0.0.3-progressive-frontier`, and `draft=false`. Include RED evidence, focused GREEN evidence, exact feature SHA, and note that schema remains v1.

- [ ] **Step 4: Require canonical GitHub Actions exact-head GREEN**

Workflow: `Nolane-AI Refoundation Epoch 0`.

Both Python 3.11 and 3.13 jobs must pass compile, 67 dossier freshness, repository audit, all Refoundation tests, zero-loss evidence generation/upload, broad regressions, and frozen Neural R2.3 verification. Do not use a successful run from an earlier head as merge evidence.

- [ ] **Step 5: Merge with expected-head protection**

Merge only if PR head SHA exactly equals the SHA that produced the final green workflow. If head moved, rerun canonical CI before merge.

- [ ] **Step 6: Post-merge verify `main`**

Fetch `main` and the merge commit. Verify:
- PR is closed and merged;
- merge commit includes the exact tested feature head as a parent;
- final main tree contains `COMPONENT_VERSION = "0.0.3"`;
- `SCHEMA_VERSION = "candidate-synthesis-v1"`;
- `SynthesisMode.PROGRESSIVE_MULTI_DEPTH_SEARCH` exists;
- component revision is 3;
- no temporary workflow carrier remains.

Only after these checks may v0.0.3 be called complete.
