# Candidate Synthesis v0.0.4 — Structural Composition Program Design

**Status:** proposed design, approved in chat for specification

**Component:** `external.candidate_synthesis`

**Target component version:** `0.0.4`

**Existing protocol:** `candidate-synthesis-v1` remains authoritative and unchanged for v0.0.1–v0.0.3 modes.

**New protocol:** `candidate-synthesis-v2` is introduced only for structural-composition requests and receipts.

## 1. Problem

Candidate Synthesis v0.0.1–v0.0.3 can compose and search learned abstractions, but its expressive language is intentionally narrow. The engine resolves only unary sources (`parameter_count == 1`), composes them as a linear chain, and always emits a unary learned abstraction. v0.0.3 therefore improves depth of search without expanding the topology of inventions it can represent.

This creates an architectural bottleneck. Cognitive Vocabulary already supports learned abstractions with arbitrary non-negative `parameter_count` and `AbstractionCall` nodes with ordered argument tuples. Capability Acquisition already transports canonical `LearnedAbstraction` payloads independently of arity. Candidate Synthesis is therefore the restricting boundary.

Optimizing permutation search before removing this restriction would make search more efficient inside an unnecessarily small hypothesis language. v0.0.4 should expand the proposal language first and leave intelligent structural search for a later revision.

## 2. Goal

Add an explicit, deterministic structural-composition mode that can compose installed learned abstractions of arbitrary arity into a finite tree program and emit one fully expanded standalone `LearnedAbstraction` candidate.

The new mode must support compositions such as:

```text
ADD(
    ABS(input0),
    NEG(input1)
)
```

and deeper trees such as:

```text
MAX(
    ADD(ABS(input0), NEG(input1)),
    ABS(input2)
)
```

without installing generated intermediates, widening Candidate Synthesis authority, or changing any v0.0.1–v0.0.3 semantics.

## 3. Non-goals

v0.0.4 does **not**:

- search automatically over structural programs;
- rank multiple structural programs;
- use a model, heuristic, Assurance score, challenge evidence, or final-verification evidence to choose topology;
- mutate Cognitive Library;
- admit, probation, promote, quarantine, revoke, or retrieve capabilities;
- create generated intermediate abstractions in a shadow vocabulary;
- change Cognitive Vocabulary semantics;
- change Capability Acquisition semantics;
- add recursive/self-referential candidate programs;
- introduce a DAG/reference graph encoding. The v0.0.4 request IR is a canonical tree. Repeated substructure is represented by repeated tree nodes.

Automatic bounded structural search is deferred to a later Candidate Synthesis revision.

## 4. Compatibility boundary

### 4.1 Existing modes remain protocol-v1

These modes retain their existing request/receipt semantics under `candidate-synthesis-v1`:

- `LEARNED_ABSTRACTION_COMPOSITION`
- `BOUNDED_LEARNED_ABSTRACTION_SEARCH`
- `PROGRESSIVE_MULTI_DEPTH_SEARCH`

Their source ordering rules, budget accounting, abstention reasons, ranking, request state, receipt state, and synthesis identities must remain behaviorally unchanged.

`SCHEMA_VERSION` remains the compatibility alias for `candidate-synthesis-v1` so existing callers and exact-state tests do not silently migrate.

### 4.2 Structural mode uses protocol-v2

Add:

```text
STRUCTURAL_COMPOSITION_PROGRAM = "structural_composition_program"
```

The structural mode must never be accepted by the legacy `SynthesisRequest` or legacy `SynthesisReceipt`. Attempting to construct a v1 request/receipt with the structural mode fails closed and directs the caller to the v2 structural protocol.

Introduce a distinct structural request/receipt contract with:

```text
STRUCTURAL_SCHEMA_VERSION = "candidate-synthesis-v2"
```

This avoids adding optional structural fields to v1 state and therefore avoids changing historical content identities.

## 5. Structural program IR

v0.0.4 introduces two immutable canonical request-IR node types.

### 5.1 Input node

Conceptually:

```text
StructuralInput(index)
```

Canonical state:

```json
{"input": 0}
```

Rules:

- `index` is an integer >= 0;
- booleans are rejected as indices;
- input nodes are placeholders for the parameters of the generated candidate;
- an input may appear multiple times;
- globally used input indices must be contiguous from zero.

If the program uses `{0, 1, 2}`, the generated abstraction has `parameter_count = 3`.

If the program uses `{0, 2}` but not `1`, the request is non-canonical and rejected.

A program may use no inputs only when its call tree can be satisfied entirely by nullary installed abstractions; the resulting candidate has `parameter_count = 0`.

### 5.2 Call node

Conceptually:

```text
StructuralCall(source_abstraction_id, args)
```

Canonical state:

```json
{
  "call": "abs.<digest>",
  "args": [
    {"input": 0},
    {"input": 1}
  ]
}
```

Rules:

- `source_abstraction_id` must identify an exact installed `LearnedAbstraction` in the current Cognitive Library;
- argument order is semantic;
- `len(args)` must equal the installed source abstraction's `parameter_count`;
- the same source abstraction may be called multiple times in one program;
- every child is another structural input or call node;
- unknown fields, non-canonical state, malformed child sequences, and empty source IDs fail closed.

### 5.3 Tree-only encoding

v0.0.4 intentionally uses a tree, not node IDs plus references. This removes aliasing, cycle, and graph-canonicalization ambiguity from the first general structural protocol.

Repeated computation such as:

```text
ADD(ABS(input0), ABS(input0))
```

is encoded by two explicit `ABS` call nodes.

## 6. Structural request

Introduce a dedicated immutable `StructuralSynthesisRequest`.

Semantic fields:

- fixed mode `STRUCTURAL_COMPOSITION_PROGRAM`;
- `objective`;
- full canonical structural `program`;
- discovery-phase evidence refs;
- experiment receipt IDs;
- causal program IDs;
- `generation_budget`.

`source_item_ids` is **derived**, not caller-authoritative. It is the sorted unique set of every source abstraction ID referenced by call nodes in the program.

The serialized v2 request includes this derived set for auditability. Restoration recomputes it from the program and rejects any mismatch. This prevents a request from claiming one source envelope while executing another.

The structural program must contain at least one call node. A raw input-only program is rejected because it does not synthesize from Cognitive Library capability.

### 6.1 Budget semantics

An explicit structural program is exactly one synthesis hypothesis.

- `generation_budget == 0` -> abstain with `generation_budget_exhausted`, considered `0`;
- `generation_budget >= 1` -> the program may be attempted once, considered `1`;
- values greater than one do not create hidden search or repeated execution.

This keeps budget semantics explicit while reserving multi-hypothesis structural search for a later mode.

## 7. Structural receipt

Introduce `StructuralSynthesisReceipt` under `candidate-synthesis-v2`.

The receipt binds:

- mode;
- objective;
- the **full canonical structural program state**;
- recomputed sorted unique `source_item_ids`;
- discovery evidence IDs;
- experiment receipt IDs;
- causal program IDs;
- generation budget;
- candidates considered;
- candidate ID or abstention reason;
- semantic fingerprint for a successful candidate;
- content-addressed synthesis ID.

The full program is carried in receipt semantic state rather than only a program digest. A receipt can therefore prove the exact wiring topology that generated its candidate without relying on a separately retained request object.

`from_state()` must reparse the program, recompute source IDs, recompute the receipt identity, and reject tampering or non-canonical state.

## 8. Compilation and expansion

Structural programs are proposal IR only. They never enter Cognitive Library.

Compilation proceeds recursively:

1. Validate the canonical tree and global input-index set.
2. Resolve each call source from the exact current Cognitive Library.
3. Validate source type and arity before composing.
4. Lower each `StructuralInput(i)` to a synthesis-reserved temporary field unique to index `i`.
5. Lower each structural call to transient canonical `AbstractionCall(source_id, compiled_args)`.
6. Expand the complete root expression against the exact existing Cognitive Vocabulary.
7. Replace the synthesis-reserved temporary fields with `TemplateParam(i)`.
8. Assert no unresolved `AbstractionCall` remains.
9. Create one standalone `LearnedAbstraction` whose `parameter_count` equals the canonical number of program inputs.
10. Convert that abstraction through the existing `CapabilityCandidate.for_learned_abstraction()` contract.

No generated intermediate expression is registered in the vocabulary and no generated candidate becomes visible to another call within the same synthesis.

## 9. Reserved-field safety

The existing unary synthesis path uses one internal reserved field. General structural composition requires one temporary reserved field per input index.

Use a dedicated internal prefix, conceptually:

```text
__nolane_candidate_synthesis_param_<index>__
```

Before structural compilation, every referenced installed source template is checked recursively. If any source contains a `Field` whose name belongs to the synthesis-reserved namespace, structural synthesis fails closed with a reserved-field-collision abstention.

The check is namespace-wide, not limited to the input indices used by the current program. This prevents a source from colliding with a future temporary parameter index.

The temporary namespace is an implementation mechanism only and never appears in the emitted candidate template.

## 10. Resource bounds

Structural expressivity must not create an unbounded parser/expander surface.

v0.0.4 defines deterministic component bounds:

- maximum structural IR nodes: `256`;
- maximum structural IR depth: `64`;
- maximum expanded cognitive-expression nodes: existing `10_000` expansion ceiling.

A request exceeding the structural node or depth limit is rejected before candidate construction. Expansion that exceeds the existing cognitive expansion bound fails closed and produces no candidate.

These are implementation safety bounds, not proposal-quality judgments.

## 11. Candidate semantics

The generated standalone abstraction is canonicalized through existing `make_abstraction()` semantics.

- `parameter_count` = number of contiguous structural inputs;
- `support_task_ids` = sorted unique union of support task IDs from every referenced source call;
- `raw_occurrence_cost` = final expanded template cost;
- `rewritten_cost` = final expanded template cost;
- abstraction identity remains content-derived from template + parameter count;
- candidate identity remains derived by Capability Acquisition's existing `CapabilityCandidate` contract.

Calling a source multiple times does not duplicate its support-task IDs.

### 11.1 Source-equivalent and installed results

If the generated abstraction identity equals any source abstraction referenced by the structural program, synthesis abstains with `candidate_matches_source`.

If the generated abstraction is already installed in Cognitive Library with the exact same payload, synthesis abstains with `candidate_already_in_library`.

If the generated abstraction identity collides with a different installed payload, synthesis fails closed with the existing collision discipline rather than selecting or mutating anything.

## 12. Evidence and authority boundary

Structural composition preserves the Candidate Synthesis authority model exactly.

Allowed during generation:

- Cognitive Library content;
- discovery-phase evidence references;
- experiment receipt IDs as provenance references;
- causal program IDs as provenance references.

Forbidden as generation authority:

- `INDEPENDENT_CHALLENGE` evidence;
- `FINAL_ASSURANCE` evidence;
- promotion receipts;
- probation state;
- final reliability decisions;
- neural mutation or training state.

The engine remains stateless with respect to lifecycle authority. It may return a `CapabilityCandidate` only. A caller must separately invoke Capability Acquisition for lifecycle admission.

Before and after every structural synthesis attempt, the Cognitive Library digest must remain identical.

## 13. Engine API

The engine may extend its public dispatch surface to accept either the legacy v1 request or the new structural v2 request, but legacy valid inputs must preserve existing behavior.

Conceptually:

```text
CandidateSynthesisEngine.synthesize(
    SynthesisRequest | StructuralSynthesisRequest
) -> SynthesisResult | StructuralSynthesisResult
```

The exact Python typing may use a shared protocol/union, but the serialized v1 and v2 contracts remain distinct.

A legacy `SynthesisRequest` cannot smuggle structural mode without a structural program. A v2 structural request cannot invoke legacy search modes.

## 14. Determinism

For a fixed:

- Cognitive Library state;
- structural request state;
- component version;

structural synthesis must produce the same candidate/abstention and exact receipt identity independent of process history.

Caller ordering of evidence, experiment IDs, causal IDs, or the derived source set is non-semantic and canonicalized. Program child order remains semantic.

Two structural programs that reference the same source set but wire arguments differently must have different request/receipt semantic states unless their canonical program states are literally identical.

If two different programs expand to the same final learned abstraction, their candidate IDs may legitimately be equal while their synthesis receipt IDs remain different because the receipts bind different program provenance.

## 15. Failure behavior

Malformed protocol state fails closed with exceptions during construction/restoration.

Valid structural requests may abstain for runtime/domain conditions such as:

- `generation_budget_exhausted`;
- `source_not_found:<id>`;
- `source_arity_mismatch:<id>`;
- `reserved_field_collision:<id>`;
- `candidate_matches_source`;
- `candidate_already_in_library`.

Program-size/depth violations are request-validation errors rather than quality abstentions because the request itself lies outside the accepted protocol envelope.

No failure path may partially mutate Cognitive Library or Capability Acquisition state.

## 16. Testing contract

Implementation must be driven by RED tests before production changes.

Minimum focused contracts:

1. component advances to `0.0.4` while legacy `SCHEMA_VERSION` remains `candidate-synthesis-v1`;
2. v0.0.1–v0.0.3 exact behavioral/state contracts stay green;
3. legacy request rejects structural mode;
4. v2 request/receipt round-trip canonically;
5. source IDs are derived from program and tampered serialized source sets are rejected;
6. binary source composition produces a valid two-parameter standalone candidate;
7. mixed unary/binary nested composition produces expected expanded template;
8. three-input nested structural program produces `parameter_count == 3`;
9. repeated use of the same source is allowed and deterministic;
10. repeated use of the same input is allowed;
11. non-contiguous input indices are rejected;
12. nullary structural candidate works when built entirely from valid nullary installed sources;
13. input-only program is rejected;
14. missing source abstains without mutation;
15. arity mismatch abstains without mutation;
16. reserved namespace collision abstains without mutation;
17. unresolved abstraction calls cannot survive candidate emission;
18. candidate matching a source abstains;
19. already-installed exact candidate abstains;
20. same-ID/different-payload library collision fails closed;
21. challenge/final-Assurance evidence remains forbidden;
22. zero generation budget considers zero hypotheses;
23. positive budget considers exactly one explicit program;
24. program node/depth limits are enforced;
25. expansion node budget is enforced;
26. library digest is unchanged on success and every abstention/error path tested;
27. Capability Acquisition remains empty until a separate explicit `admit()`;
28. explicit admission after structural synthesis yields only `CapabilityState.CANDIDATE`;
29. two different wiring programs over the same source set receive distinct synthesis receipt identities;
30. two different wiring programs that expand to the same candidate preserve candidate identity equality but receipt provenance inequality.

Run focused Refoundation suites under Python 3.11 and 3.13, then the canonical Refoundation workflow and broad coding-AGI regressions on the exact final feature head before merge.

## 17. Expected implementation scope

Primary files expected to change:

- `nolane/external_core/candidate_synthesis.py`
- `nolane/metadata/component_versions.py`
- focused Candidate Synthesis tests, including a new structural-composition suite;
- `CURRENT/EXTERNAL_CORE.md` after behavior is green;
- this design spec and its implementation plan.

No production changes are expected in:

- `cognitive_vocabulary.py`;
- `cognitive_library.py`;
- `capability_acquisition.py`;
- `assurance.py`;
- neural code.

If implementation discovers that one of those boundaries must change, the task is reclassified and this design must be revised before continuing.

## 18. Version progression

The intended progression becomes:

```text
v0.0.1  explicit unary composition
v0.0.2  bounded ordered-pair unary search
v0.0.3  progressive multi-depth unary search
v0.0.4  explicit general structural composition
v0.0.5  bounded structural-program search
v0.0.6  intelligent structural search policy
v0.0.7+ objective/evidence/causal-guided invention, subject to separate authority design
```

v0.0.4 therefore expands what Candidate Synthesis can represent before later revisions optimize how that larger space is explored.

## 19. Acceptance criteria

v0.0.4 is complete only when all of the following hold:

- structural composition can consume installed learned abstractions with arbitrary valid arity;
- the result is one standalone canonical abstraction with no unresolved calls;
- exact structural wiring is content-bound in v2 request/receipt provenance;
- old v1 modes retain their established semantics and identities;
- no shadow library or generated intermediate vocabulary exists;
- no Candidate Synthesis lifecycle/Assurance authority is added;
- deterministic resource bounds are enforced;
- RED evidence demonstrates the new behavior was absent before production changes;
- focused and broad regression suites pass on supported Python versions;
- final PR is non-draft, exact-head CI is green, merge uses an expected-head guard, and post-merge `main` is verified content-equivalent to the tested feature tree.
