# Candidate Synthesis v0.0.4 Structural Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `external.candidate_synthesis` from unary-chain-only proposal synthesis to an explicit canonical structural-composition program that can compose installed learned abstractions of arbitrary arity into one fully expanded standalone `CapabilityCandidate`, without changing v0.0.1-v0.0.3 behavior or widening lifecycle authority.

**Architecture:** Keep the existing v1 protocol and three legacy modes byte/semantically stable. Add a separate v2 structural protocol (`StructuralInput`, `StructuralCall`, `StructuralSynthesisRequest`, `StructuralSynthesisReceipt`, `StructuralSynthesisResult`) and one new `STRUCTURAL_COMPOSITION_PROGRAM` mode. Compile the request tree to transient `AbstractionCall` IR against the exact existing Cognitive Library, expand it completely, bind temporary input fields to `TemplateParam`, and emit one standalone learned abstraction; do not create a shadow vocabulary or modify Capability Acquisition.

**Tech Stack:** Python 3.11/3.13, frozen dataclasses, stdlib typing/collections, existing canonical digest contracts, `CognitiveLibrary`, `CognitiveVocabulary`, `AbstractionCall`, `TemplateParam`, `CapabilityCandidate`, pytest, canonical GitHub Actions Refoundation workflow.

**Spec:** `docs/superpowers/specs/2026-08-30-candidate-synthesis-v0.0.4-structural-composition-design.md`

## Global Constraints

- `external.candidate_synthesis` advances exactly from `0.0.3` to `0.0.4`.
- Legacy `SCHEMA_VERSION` remains exactly `candidate-synthesis-v1`.
- Add `STRUCTURAL_SCHEMA_VERSION = "candidate-synthesis-v2"` only for structural request/receipt state.
- Existing `LEARNED_ABSTRACTION_COMPOSITION`, `BOUNDED_LEARNED_ABSTRACTION_SEARCH`, and `PROGRESSIVE_MULTI_DEPTH_SEARCH` semantics and v1 identities remain unchanged.
- Add exactly one new mode: `STRUCTURAL_COMPOSITION_PROGRAM = "structural_composition_program"`.
- Legacy `SynthesisRequest`/`SynthesisReceipt` reject structural mode.
- Structural IR is a finite canonical tree; repeated substructure is repeated tree nodes, not graph references.
- Static request validation owns canonical shape, node/depth bounds, contiguous input indices, provenance normalization, and derived source IDs.
- Library-bound synthesis validation owns exact source existence, learned-abstraction type, source arity, and reserved-field collision checks.
- Maximum structural IR nodes: `256`; maximum structural IR depth: `64`; expanded expression limit remains `10_000` nodes.
- An explicit structural program counts as exactly one hypothesis: budget 0 -> considered 0 / `generation_budget_exhausted`; budget >=1 -> exactly one attempt.
- Structural candidate `parameter_count` equals contiguous program input count; nullary composition is valid when the entire program is satisfied by installed nullary abstractions.
- Structural receipt semantic state binds the complete canonical wiring program and recomputed source IDs.
- Candidate Synthesis remains discovery-only, stateless, and has no admit/probation/Assurance/promotion/quarantine/revocation/Neural authority.
- No production changes to `cognitive_vocabulary.py`, `cognitive_library.py`, `capability_acquisition.py`, `assurance.py`, or neural code are permitted under this plan. If required, stop and revise the design.
- RED must fail for intended missing v0.0.4 behavior only; setup/fixture/oracle failure does not count.
- Exact final feature-head CI must pass on Python 3.11 and 3.13 before non-draft PR merge; merge must use expected-head guard; post-merge `main` must be verified content-identical to the tested feature tree.

---

### Task 1: Lock v0.0.4 RED contracts

**Files:**
- Create: `tests/test_refoundation_post_epoch0_candidate_synthesis_structural_composition.py`
- Modify: `tests/test_refoundation_post_epoch0_candidate_synthesis.py`
- Modify: `tests/test_refoundation_post_epoch0_candidate_synthesis_bounded_search.py`
- Modify: `tests/test_refoundation_post_epoch0_candidate_synthesis_progressive_frontier.py`
- Modify: `tests/test_refoundation_component_versions.py`

**Interfaces:**
- Consumes: existing `CandidateSynthesisEngine`, v1 request/receipt API, `CognitiveLibrary`, `LearnedAbstraction`, `CapabilityAcquisitionGovernor`.
- Produces: failing contracts for v0.0.4 symbols/semantics and updated current-version declarations while preserving legacy behavior tests.

- [ ] **Step 1: Advance declaration expectations only**

Update current component assertions from `0.0.3` to `0.0.4` in the three existing Candidate Synthesis suites, while keeping every assertion of `candidate-synthesis-v1` unchanged. Set:

```python
ACCEPTED_COMPONENT_REVISIONS["external.candidate_synthesis"] = 4
```

in `tests/test_refoundation_component_versions.py`.

- [ ] **Step 2: Create structural API loader and canonical fixtures**

The new test file imports the v0.0.4 surface through a helper so RED is a clean missing-production-symbol failure:

```python
def _structural_api():
    try:
        from nolane.external_core.candidate_synthesis import (
            STRUCTURAL_SCHEMA_VERSION,
            CandidateSynthesisEngine,
            EvidencePhase,
            EvidenceRef,
            StructuralCall,
            StructuralInput,
            StructuralSynthesisReceipt,
            StructuralSynthesisRequest,
            StructuralSynthesisResult,
            SynthesisMode,
        )
    except ImportError as exc:
        pytest.fail(f"production structural synthesis API is missing: {exc}")
    return (
        STRUCTURAL_SCHEMA_VERSION,
        CandidateSynthesisEngine,
        EvidencePhase,
        EvidenceRef,
        StructuralCall,
        StructuralInput,
        StructuralSynthesisReceipt,
        StructuralSynthesisRequest,
        StructuralSynthesisResult,
        SynthesisMode,
    )
```

Build installed fixtures for unary `abs`, unary `neg`, binary `add`, binary `max`, and nullary constant abstractions with canonical `TemplateParam` templates.

- [ ] **Step 3: Lock protocol-v2 canonicalization**

Add tests proving:

```python
assert STRUCTURAL_SCHEMA_VERSION == "candidate-synthesis-v2"
assert request.to_state()["schema_version"] == "candidate-synthesis-v2"
assert request.source_item_ids == tuple(sorted({all_call_source_ids}))
assert StructuralSynthesisRequest.from_state(request.to_state()) == request
```

Reverse evidence/experiment/causal caller order and prove request equality. Tamper serialized `source_item_ids` and require `ValueError` on restore.

- [ ] **Step 4: Lock v1/v2 separation**

Construct legacy `SynthesisRequest(mode=SynthesisMode.STRUCTURAL_COMPOSITION_PROGRAM, ...)` and require fail-closed `ValueError` mentioning structural/v2. Also prove structural request has fixed structural mode and cannot be restored with a legacy mode value.

- [ ] **Step 5: Lock structural expressivity**

Cover these concrete programs:

```python
StructuralCall(add_id, (
    StructuralCall(abs_id, (StructuralInput(0),)),
    StructuralCall(neg_id, (StructuralInput(1),)),
))
```

Expected candidate: `parameter_count == 2`, union support IDs, no `call` in final template, exact expected `Binary("add", Unary("abs", TemplateParam(0)), Unary("neg", TemplateParam(1)))` state.

Also cover a nested three-input tree using `max(add(abs(input0), neg(input1)), abs(input2))`, repeated source use, repeated input use, and a nullary call tree producing `parameter_count == 0`.

- [ ] **Step 6: Lock static protocol failures**

Require request construction/restoration to reject:

```text
input-only root
negative/bool input index
non-contiguous inputs {0,2}
unknown node fields
malformed args sequence
empty call source id
>256 nodes
>64 depth
challenge/final-Assurance evidence
```

These are construction/restoration errors, not runtime abstentions.

- [ ] **Step 7: Lock library-bound runtime abstentions/errors**

Require valid requests to produce deterministic outcomes for:

```text
budget 0 -> generation_budget_exhausted / considered 0
missing source -> source_not_found:<id> / considered 1
arity mismatch -> source_arity_mismatch:<id> / considered 1
reserved namespace source field -> reserved_field_collision:<id> / considered 1
candidate equal to referenced source -> candidate_matches_source / considered 1
exact installed result -> candidate_already_in_library / considered 1
same generated ID bound to forged different payload -> ValueError collision
expansion >10000 nodes -> fail closed, no candidate, no mutation
```

- [ ] **Step 8: Lock provenance identity semantics**

Build two programs over the same source set with different child wiring and assert distinct structural receipt IDs. Build two distinct programs that expand to the same final abstraction and assert candidate IDs equal while synthesis receipt IDs differ.

- [ ] **Step 9: Lock authority invariants**

On success and representative abstentions/errors:

```python
library_before = library.digest
governor_before = governor.digest
result = engine.synthesize(request)
assert library.digest == library_before
assert governor.digest == governor_before
assert governor.records() == ()
```

After a successful structural result, a separate explicit `governor.admit(result.candidate)` may produce exactly `CapabilityState.CANDIDATE`, never probation/promotion.

- [ ] **Step 10: Commit RED-only changes and open non-draft PR**

Commit only tests/declaration expectations. Open the feature PR as non-draft so canonical PR CI supplies RED evidence. The PR body must label this run as expected RED and name the exact intended failures.

Expected RED: missing structural symbols/mode and component still reporting 0.0.3. Existing v0.0.1-v0.0.3 behavioral tests must otherwise remain green.

---

### Task 2: Implement the v2 structural protocol surface

**Files:**
- Modify: `nolane/external_core/candidate_synthesis.py`
- Modify: `nolane/metadata/component_versions.py`

**Interfaces:**
- Consumes: `canonical_digest`, existing `EvidenceRef`/`EvidencePhase`, existing `SynthesisMode`.
- Produces: `StructuralInput`, `StructuralCall`, `StructuralSynthesisRequest`, structural parser/helpers, `StructuralSynthesisReceipt`, `StructuralSynthesisResult`, new constants/mode, revision 4.

- [ ] **Step 1: Add version constants and mode without touching legacy schema**

```python
COMPONENT_VERSION = "0.0.4"
SCHEMA_VERSION = "candidate-synthesis-v1"
STRUCTURAL_SCHEMA_VERSION = "candidate-synthesis-v2"
MAX_STRUCTURAL_NODES = 256
MAX_STRUCTURAL_DEPTH = 64
_RESERVED_PARAM_PREFIX = "__nolane_candidate_synthesis_param_"

class SynthesisMode(str, Enum):
    LEARNED_ABSTRACTION_COMPOSITION = "learned_abstraction_composition"
    BOUNDED_LEARNED_ABSTRACTION_SEARCH = "bounded_learned_abstraction_search"
    PROGRESSIVE_MULTI_DEPTH_SEARCH = "progressive_multi_depth_search"
    STRUCTURAL_COMPOSITION_PROGRAM = "structural_composition_program"
```

Set `"external.candidate_synthesis": 4` in metadata.

- [ ] **Step 2: Make legacy request/receipt reject structural mode**

At the start of legacy request/receipt normalization after enum conversion:

```python
if mode is SynthesisMode.STRUCTURAL_COMPOSITION_PROGRAM:
    raise ValueError("structural composition requires candidate-synthesis-v2 protocol")
```

Do not otherwise modify v1 state layout or identity calculation.

- [ ] **Step 3: Add immutable structural IR nodes**

Implement `StructuralInput(index: int)` and `StructuralCall(source_abstraction_id: str, args: tuple[StructuralNode, ...])` with exact `to_state()` methods:

```python
{"input": index}
{"call": source_id, "args": [child.to_state(), ...]}
```

Add `_structural_node_from_state()` that accepts exactly one canonical node shape and rejects unknown/missing fields through round-trip equality.

- [ ] **Step 4: Add static tree analysis**

Implement one traversal returning node count, max depth, sorted used input indices, sorted unique source IDs, and call count. Enforce:

```python
node_count <= 256
max_depth <= 64
call_count >= 1
used_inputs == tuple(range(len(used_inputs)))
```

Do not resolve Cognitive Library in this traversal.

- [ ] **Step 5: Add StructuralSynthesisRequest**

Use fixed mode and fields:

```python
@dataclass(frozen=True, slots=True)
class StructuralSynthesisRequest:
    program: StructuralNode
    objective: str
    evidence: tuple[EvidenceRef, ...] = ()
    experiment_receipt_ids: tuple[str, ...] = ()
    causal_program_ids: tuple[str, ...] = ()
    generation_budget: int = 1
    mode: SynthesisMode = SynthesisMode.STRUCTURAL_COMPOSITION_PROGRAM
```

Normalize discovery-only evidence and set-like provenance exactly as v1. Derive `source_item_ids` from the canonical program; expose it as a property. Serialize v2 state including the full program and derived source IDs. `from_state()` reparses the program, reconstructs the request, and rejects any mismatch between serialized and derived source IDs or any non-canonical state.

- [ ] **Step 6: Add StructuralSynthesisReceipt and result**

Receipt semantic state includes full program, derived source IDs, normalized provenance, budget, considered count, candidate/fingerprint/reason and content-addressed `synthesis_id`. Its constructor validates success-vs-abstention shape and recomputes identity. `from_state()` reparses program and rejects tampering.

`StructuralSynthesisResult` mirrors legacy result checks but requires `StructuralSynthesisReceipt`.

- [ ] **Step 7: Run focused protocol tests**

Run structural protocol/static-validation tests plus all legacy Candidate Synthesis suites. Expected: protocol/static tests green; execution tests still RED because structural compiler/dispatch is not implemented. Legacy semantics remain green except current-version expectations now correctly report 0.0.4.

- [ ] **Step 8: Commit protocol surface**

Commit structural protocol and revision advancement separately from compiler behavior.

---

### Task 3: Implement library-bound structural compilation and standalone candidate emission

**Files:**
- Modify: `nolane/external_core/candidate_synthesis.py`
- Test: `tests/test_refoundation_post_epoch0_candidate_synthesis_structural_composition.py`

**Interfaces:**
- Consumes: `StructuralSynthesisRequest`, exact current `CognitiveLibrary`, `AbstractionCall`, `expand_expr`, `make_abstraction`, `CapabilityCandidate.for_learned_abstraction`.
- Produces: deterministic `StructuralSynthesisResult` for one explicit structural hypothesis.

- [ ] **Step 1: Add reserved namespace helpers**

Implement:

```python
def _reserved_param_field(index: int) -> str:
    return f"{_RESERVED_PARAM_PREFIX}{index}__"


def _contains_reserved_param_field(expr: Expr) -> bool:
    ...
```

The collision check is prefix-wide, not limited to currently used indices.

- [ ] **Step 2: Add multi-input binder**

Implement a recursive binder that converts only exact generated temporary field names to `TemplateParam(index)`, preserves ordinary fields/operators/constants, and raises if an `AbstractionCall` survives expansion.

- [ ] **Step 3: Resolve and validate every structural call against the exact library**

For each call node during compilation:

```text
lookup source ID
if missing -> runtime abstention source_not_found:<id>
if retrieved value is not LearnedAbstraction -> fail closed
if len(call.args) != source.parameter_count -> runtime abstention source_arity_mismatch:<id>
if source template contains reserved prefix -> runtime abstention reserved_field_collision:<id>
```

Repeated calls to the same installed source are valid. Validation must not register anything.

- [ ] **Step 4: Lower the canonical structural tree**

Compile recursively:

```python
StructuralInput(i) -> Field(_reserved_param_field(i))
StructuralCall(id, args) -> AbstractionCall(id, tuple(compile(child) for child in args))
```

Collect support task IDs as the sorted unique union of all referenced source calls.

- [ ] **Step 5: Expand and emit**

Use the existing exact vocabulary:

```python
expanded = expand_expr(lowered, self.library.vocabulary, max_expansion_nodes=10_000)
template = _bind_structural_parameters(expanded)
generated = make_abstraction(
    template,
    parameter_count=request.parameter_count,
    support_task_ids=support_task_ids,
    raw_occurrence_cost=template.cost,
    rewritten_cost=template.cost,
)
```

Assert/ensure the emitted template has no unresolved `AbstractionCall` and no generated reserved fields.

- [ ] **Step 6: Apply dedup/collision discipline**

If generated ID equals any `request.source_item_ids`, abstain `candidate_matches_source`. If `_installed_abstraction(generated)` returns exact payload, abstain `candidate_already_in_library`; if same ID maps to different payload, preserve existing fail-closed `ValueError` behavior.

- [ ] **Step 7: Add structural receipt helper and dispatch**

Budget 0 returns structural abstention considered 0 before library-bound work. Positive budget attempts exactly once and all runtime/domain abstentions after the attempt report considered 1. Extend `CandidateSynthesisEngine.synthesize()` to dispatch by request type without changing legacy branches:

```python
if isinstance(request, StructuralSynthesisRequest):
    return self._synthesize_structural(request)
if not isinstance(request, SynthesisRequest):
    raise TypeError(...)
# existing v1 logic unchanged below
```

- [ ] **Step 8: Run focused GREEN tests**

Run all four Candidate Synthesis suites plus component versions on Python 3.11 and 3.13. Fix only root causes within the approved component boundary.

- [ ] **Step 9: Commit compiler behavior**

Commit once structural success/abstention/identity/authority tests are green.

---

### Task 4: Harden resource bounds, provenance, and legacy non-regression

**Files:**
- Modify: `tests/test_refoundation_post_epoch0_candidate_synthesis_structural_composition.py`
- Modify only if a proven bug requires it: `nolane/external_core/candidate_synthesis.py`

**Interfaces:**
- Consumes: complete v0.0.4 implementation.
- Produces: adversarial proof that the new expressive surface remains deterministic and bounded.

- [ ] **Step 1: Verify exact node/depth boundary behavior**

Add boundary tests for exactly 256 nodes / 64 depth when constructible and one-over-limit rejection. Ensure recursion in validation does not accidentally accept an over-limit tree.

- [ ] **Step 2: Force expansion-budget failure**

Create compact installed abstractions whose nested expansion exceeds `10_000` nodes while request IR stays inside 256/64. Prove no candidate/library mutation and fail-closed behavior.

- [ ] **Step 3: Verify source/provenance rebinding resistance**

Prove serialized receipt source set/program tampering is rejected and a receipt cannot be restored with the same `synthesis_id` after program wiring changes.

- [ ] **Step 4: Verify old exact identities on unchanged inputs**

Use existing legacy request fixtures and ensure v1 `to_state()`, canonical source ordering, abstention reasons and candidate/receipt identity behavior are unchanged except the component declaration version itself.

- [ ] **Step 5: Run broad local/canonical test target**

Run the full Refoundation test suite available in CI after focused suites. Any unrelated failure triggers systematic debugging before modification.

- [ ] **Step 6: Commit hardening**

Commit only test hardening plus any minimal proven production fix.

---

### Task 5: Document, exact-head verify, review, merge, and prove main

**Files:**
- Modify: `CURRENT/EXTERNAL_CORE.md`
- Existing: design spec and this plan
- No temporary workflow carrier may remain in final diff.

**Interfaces:**
- Consumes: green v0.0.4 exact feature tree.
- Produces: repository authority/documentation update, canonical CI evidence, reviewed non-draft PR, expected-head merge, post-merge tree proof.

- [ ] **Step 1: Update canonical External Core documentation**

Document v0.0.4 as explicit structural composition: separate v2 protocol, arbitrary source arity, tree wiring, full expansion to standalone candidate, one-hypothesis budget semantics, resource bounds, and unchanged discovery-only/lifecycle authority.

- [ ] **Step 2: Inspect final diff for scope**

Expected persistent production/doc/test scope:

```text
CURRENT/EXTERNAL_CORE.md
docs/superpowers/specs/2026-08-30-candidate-synthesis-v0.0.4-structural-composition-design.md
docs/superpowers/plans/2026-08-30-candidate-synthesis-v0.0.4-structural-composition.md
nolane/external_core/candidate_synthesis.py
nolane/metadata/component_versions.py
tests/test_refoundation_component_versions.py
tests/test_refoundation_post_epoch0_candidate_synthesis.py
tests/test_refoundation_post_epoch0_candidate_synthesis_bounded_search.py
tests/test_refoundation_post_epoch0_candidate_synthesis_progressive_frontier.py
tests/test_refoundation_post_epoch0_candidate_synthesis_structural_composition.py
```

Any other production file requires explicit architectural justification or removal.

- [ ] **Step 3: Run exact final-head canonical CI**

Require both supported Python versions to pass compile, dossier/audit, all Refoundation tests, zero-loss evidence generation, broad coding-AGI regressions, and Neural contract gates. Record exact run/job IDs and test counts from logs.

- [ ] **Step 4: Perform independent structured code review**

Review spec vs diff vs tests for: v1 identity drift, structural canonicalization holes, arity/source validation order, mutation leaks, unresolved calls, reserved-field collisions, resource-bound bypasses, hidden Assurance authority, and scope creep. Resolve any finding and rerun exact-head CI if the tree changes.

- [ ] **Step 5: Finalize PR and merge with expected-head guard**

Update PR body with RED evidence, GREEN evidence, authority/scope proof and exact final feature SHA. Confirm non-draft/mergeable and merge only with `expected_head_sha=<exact tested feature head>`.

- [ ] **Step 6: Post-merge verification**

Verify `main` points to the merge commit, merge parents include exact tested base and exact tested feature head, signature is valid when available, and compare tested feature head -> merge commit returns no file differences. Re-read `candidate_synthesis.py` and component metadata on `main` to confirm `0.0.4`, legacy `candidate-synthesis-v1`, structural `candidate-synthesis-v2`, and the structural mode.
