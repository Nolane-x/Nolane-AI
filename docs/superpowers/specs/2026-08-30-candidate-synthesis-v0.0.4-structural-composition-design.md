# Candidate Synthesis v0.0.4 — Structural Composition Program Design

**Status:** proposed design, approved in chat for specification

**Component:** `external.candidate_synthesis`

**Target component version:** `0.0.4`

**Existing protocol:** `candidate-synthesis-v1` remains authoritative and unchanged for v0.0.1–v0.0.3 modes.

**New protocol:** `candidate-synthesis-v2` is introduced only for structural-composition requests and receipts.

## 1. Problem

Candidate Synthesis v0.0.1–v0.0.3 can compose and search learned abstractions, but its expressive language is intentionally narrow. The engine resolves only unary sources (`parameter_count == 1`), composes them as a linear chain, and always emits a unary learned abstraction. v0.0.3 therefore improves depth of search without expanding the topology of inventions it can represent.

Cognitive Vocabulary already supports learned abstractions with arbitrary non-negative `parameter_count` and `AbstractionCall` nodes with ordered argument tuples. Capability Acquisition already transports canonical `LearnedAbstraction` payloads independently of arity. Candidate Synthesis is therefore the restricting boundary.

Optimizing permutation search before removing this restriction would make search more efficient inside an unnecessarily small hypothesis language. v0.0.4 expands the proposal language first; intelligent structural search remains a later revision.

## 2. Goal

Add an explicit, deterministic structural-composition mode that can compose installed learned abstractions of arbitrary arity into a finite tree program and emit one fully expanded standalone `LearnedAbstraction` candidate.

Examples:

```text
ADD(
    ABS(input0),
    NEG(input1)
)
```

```text
MAX(
    ADD(ABS(input0), NEG(input1)),
    ABS(input2)
)
```

The mode must not install generated intermediates, widen Candidate Synthesis authority, or change v0.0.1–v0.0.3 semantics.

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

Their source-ordering rules, budget accounting, abstention reasons, ranking, request state, receipt state, and synthesis identities remain behaviorally unchanged.

`SCHEMA_VERSION` remains the compatibility alias for `candidate-synthesis-v1` so existing callers and exact-state tests do not silently migrate.

### 4.2 Structural mode uses protocol-v2

Add:

```text
STRUCTURAL_COMPOSITION_PROGRAM = "structural_composition_program"
```

The structural mode must never be accepted by legacy `SynthesisRequest` or legacy `SynthesisReceipt`. Constructing a v1 request/receipt with the structural mode fails closed and directs the caller to the v2 structural protocol.

Introduce:

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

Static rules:

- `index` is an integer >= 0;
- booleans are rejected as indices;
- input nodes are placeholders for generated candidate parameters;
- an input may appear multiple times;
- globally used input indices must be contiguous from zero.

If the program uses `{0, 1, 2}`, the generated abstraction has `parameter_count = 3`.

If the program uses `{0, 2}` but not `1`, the request is non-canonical and rejected.

A program may use no inputs. Such a request can succeed only if library-bound validation proves that the complete call tree can be satisfied by nullary installed abstractions; the resulting candidate then has `parameter_count = 0`.

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

Static protocol rules:

- source ID is non-empty;
- argument order is semantic;
- the same source ID may appear multiple times;
- every child is another structural input or call node;
- unknown fields, malformed child sequences, or non-canonical state fail closed.

Library-bound rules, evaluated only by a `CandidateSynthesisEngine` with an exact Cognitive Library state:

- the source ID must resolve to an installed `LearnedAbstraction`;
- `len(args)` must equal that installed abstraction's `parameter_count`;
- the source template must not collide with the synthesis-reserved field namespace.

A structurally valid request may therefore be constructed without a Cognitive Library and later abstain deterministically when evaluated against a library where a source is missing, has different arity, or violates reserved-field safety.

### 5.3 Tree-only encoding

v0.0.4 intentionally uses a tree, not node IDs plus references. This removes aliasing, cycle, and graph-canonicalization ambiguity from the first general structural protocol.

Repeated computation such as:

```text
ADD(ABS(input0), ABS(input0))
```

is encoded by two explicit `ABS` call nodes.

### 5.4 Two validation phases

The implementation must keep protocol validity and library-bound validity separate.

**Static request validation** has no library dependency and covers:

- canonical node shapes;
- non-empty source IDs;
- contiguous input indices;
- at least one call node;
- evidence phase rules;
- sorted/deduplicated set-like provenance;
- generation-budget type/range;
- structural node/depth limits;
- exact v2 serialization.

**Library-bound synthesis validation** occurs after budget admission and covers:

- source existence;
- source type;
- source arity;
- reserved-field collision;
- expansion safety;
- generated-source equivalence;
- already-installed candidates;
- generated identity collisions.

This split is normative. Implementations must not move missing-source or arity checks into request construction, because doing so would make request semantics depend on ambient library state and break portable content-addressed request identity.

## 6. Structural request

Introduce immutable `StructuralSynthesisRequest`.

Semantic fields:

- fixed mode `STRUCTURAL_COMPOSITION_PROGRAM`;
- `objective`;
- full canonical structural `program`;
- discovery-phase evidence refs;
- experiment receipt IDs;
- causal program IDs;
- `generation_budget`.

`source_item_ids` is **derived**, never caller-authoritative. It is the sorted unique set of every source ID referenced by call nodes in the program.

Serialized v2 request state includes this derived set for auditability. Restoration recomputes it from the program and rejects any mismatch. This prevents a request from claiming one source envelope while executing another.

The program must contain at least one call node. An input-only program is rejected statically because it does not synthesize from Cognitive Library capability.

### 6.1 Budget semantics

An explicit structural program is exactly one synthesis hypothesis.

- `generation_budget == 0` -> abstain `generation_budget_exhausted`, considered `0`, before library-bound validation;
- `generation_budget >= 1` -> attempt the program exactly once, considered `1`;
- values greater than one do not create hidden search or repeated execution.

Checking the zero budget before source resolution is normative and mirrors the hard-budget role of existing search modes.

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
- semantic fingerprint for success;
- content-addressed synthesis ID.

The full program is carried in receipt semantic state rather than only a digest. The receipt therefore proves exact wiring topology without requiring a separately retained request object.

`from_state()` reparses the program, recomputes source IDs and receipt identity, and rejects tampering or non-canonical state.

## 8. Compilation and expansion

Structural programs are proposal IR only. They never enter Cognitive Library.

Compilation proceeds:

1. statically validate canonical tree and global input-index set;
2. after budget admission, resolve every call source from the exact current Cognitive Library;
3. validate source type, arity, and reserved namespace safety;
4. lower each `StructuralInput(i)` to a synthesis-reserved temporary field unique to index `i`;
5. lower each structural call to transient `AbstractionCall(source_id, compiled_args)`;
6. expand the complete root against the exact existing Cognitive Vocabulary;
7. replace synthesis-reserved temporary fields with `TemplateParam(i)`;
8. assert no unresolved `AbstractionCall` remains;
9. create one standalone `LearnedAbstraction` whose `parameter_count` equals the canonical number of program inputs;
10. convert it through `CapabilityCandidate.for_learned_abstraction()`.

No generated intermediate is registered in the vocabulary and no generated candidate becomes visible to another call within the same synthesis.

## 9. Reserved-field safety

General structural composition requires one temporary reserved field per input index. Use a dedicated internal namespace conceptually shaped as:

```text
__nolane_candidate_synthesis_param_<index>__
```

Before structural compilation, every referenced installed source template is checked recursively. If any source contains a `Field` whose name belongs to the synthesis-reserved namespace, structural synthesis abstains with `reserved_field_collision:<id>`.

The check is namespace-wide, not limited to indices used in the current program. This prevents collision with future temporary parameter indices.

The temporary namespace is an implementation mechanism only and never appears in an emitted candidate template.

## 10. Resource bounds

Structural expressivity must not create an unbounded parser/expander surface.

v0.0.4 defines deterministic component bounds:

- maximum structural IR nodes: `256`;
- maximum structural IR depth: `64`;
- maximum expanded cognitive-expression nodes: existing `10_000` expansion ceiling.

Node/depth violations are static request-validation failures. Expansion overflow occurs during library-bound synthesis and produces no candidate.

These are safety bounds, not proposal-quality judgments.

## 11. Candidate semantics

The generated standalone abstraction uses existing `make_abstraction()` semantics.

- `parameter_count` = number of contiguous structural inputs;
- `support_task_ids` = sorted unique union of support task IDs from every referenced source call;
- `raw_occurrence_cost` = final expanded template cost;
- `rewritten_cost` = final expanded template cost;
- abstraction identity remains content-derived from template + parameter count;
- candidate identity remains derived by the existing `CapabilityCandidate` contract.

Calling a source multiple times does not duplicate support-task IDs.

### 11.1 Source-equivalent and installed results

If generated abstraction identity equals any source abstraction referenced by the program, abstain `candidate_matches_source`.

If the generated abstraction is already installed with the exact same payload, abstain `candidate_already_in_library`.

If generated identity collides with a different installed payload, fail closed with existing collision discipline rather than selecting or mutating anything.

## 12. Evidence and authority boundary

Structural composition preserves Candidate Synthesis authority exactly.

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

The engine may return a `CapabilityCandidate` only. Lifecycle admission remains a separate Capability Acquisition call.

Cognitive Library digest must be identical before and after every structural synthesis success, abstention, and handled failure path.

## 13. Engine API

The engine may extend public dispatch to accept legacy v1 or structural v2 requests while preserving behavior for every valid legacy input.

Conceptually:

```text
CandidateSynthesisEngine.synthesize(
    SynthesisRequest | StructuralSynthesisRequest
) -> SynthesisResult | StructuralSynthesisResult
```

Exact typing may use a union/shared protocol, but serialized v1 and v2 contracts remain distinct.

A legacy `SynthesisRequest` cannot smuggle structural mode without a structural program. A v2 structural request cannot invoke legacy modes.

## 14. Determinism

For fixed Cognitive Library state, structural request state, and component version, synthesis produces the same candidate/abstention and exact receipt identity independent of process history.

Caller ordering of evidence, experiment IDs, causal IDs, or derived source set is non-semantic and canonicalized. Program child order is semantic.

Two programs referencing the same source set but wiring arguments differently have different request/receipt semantic states unless their canonical program states are identical.

Two different programs may expand to the same final learned abstraction. When their final canonical payloads are equal, candidate IDs are equal while synthesis receipt IDs remain different because receipts bind different program provenance.

## 15. Failure behavior

Malformed protocol state fails closed during construction/restoration.

Statically valid structural requests may abstain during library-bound synthesis for:

- `generation_budget_exhausted`;
- `source_not_found:<id>`;
- `source_arity_mismatch:<id>`;
- `reserved_field_collision:<id>`;
- `candidate_matches_source`;
- `candidate_already_in_library`.

Program-size/depth violations are static request-validation errors. Expansion overflow and generated identity collision fail closed and produce no candidate.

No path may partially mutate Cognitive Library or Capability Acquisition state.

## 16. Testing contract

Implementation is driven by RED tests before production changes.

Minimum focused contracts:

1. component advances to `0.0.4` while legacy `SCHEMA_VERSION` remains `candidate-synthesis-v1`;
2. v0.0.1–v0.0.3 exact behavioral/state contracts stay green;
3. legacy request rejects structural mode;
4. v2 request/receipt round-trip canonically;
5. source IDs are derived from program and tampered serialized source sets are rejected;
6. request construction succeeds without a library for syntactically valid unknown source IDs;
7. the same request later abstains `source_not_found` against a library lacking that source;
8. binary source composition produces a valid two-parameter standalone candidate;
9. mixed unary/binary nested composition produces expected expanded template;
10. three-input nested program produces `parameter_count == 3`;
11. repeated use of the same source is allowed and deterministic;
12. repeated use of the same input is allowed;
13. non-contiguous input indices are rejected statically;
14. nullary candidate works when built entirely from valid nullary sources;
15. input-only program is rejected statically;
16. arity mismatch abstains without mutation;
17. reserved namespace collision abstains without mutation;
18. unresolved abstraction calls cannot survive candidate emission;
19. candidate matching a source abstains;
20. already-installed exact candidate abstains;
21. same-ID/different-payload library collision fails closed;
22. challenge/final-Assurance evidence remains forbidden;
23. zero budget considers zero hypotheses **before** missing-source/arity checks;
24. positive budget considers exactly one explicit program;
25. program node/depth limits are enforced statically;
26. expansion node budget is enforced;
27. library digest is unchanged on success and all tested abstention/error paths;
28. Capability Acquisition remains empty until separate explicit `admit()`;
29. explicit admission yields only `CapabilityState.CANDIDATE`;
30. different wiring over the same source set yields distinct receipt identities;
31. different wiring that expands to an equal final canonical payload preserves candidate identity equality but receipt provenance inequality.

Run focused Refoundation suites on Python 3.11 and 3.13, then canonical Refoundation workflow and broad coding-AGI regressions on the exact final feature head before merge.

## 17. Expected implementation scope

Expected production changes:

- `nolane/external_core/candidate_synthesis.py`
- `nolane/metadata/component_versions.py`

Expected supporting changes:

- focused Candidate Synthesis tests, including a new structural-composition suite;
- `CURRENT/EXTERNAL_CORE.md` after behavior is green;
- this design spec and its implementation plan.

No production changes are expected in:

- `cognitive_vocabulary.py`;
- `cognitive_library.py`;
- `capability_acquisition.py`;
- `assurance.py`;
- neural code.

If implementation discovers one of those boundaries must change, stop and revise this design before continuing.

## 18. Version progression

```text
v0.0.1  explicit unary composition
v0.0.2  bounded ordered-pair unary search
v0.0.3  progressive multi-depth unary search
v0.0.4  explicit general structural composition
v0.0.5  bounded structural-program search
v0.0.6  intelligent structural search policy
v0.0.7+ objective/evidence/causal-guided invention, subject to separate authority design
```

v0.0.4 expands what Candidate Synthesis can represent before later revisions optimize how that larger space is explored.

## 19. Acceptance criteria

v0.0.4 is complete only when all hold:

- structural composition consumes installed learned abstractions with arbitrary valid arity;
- result is one standalone canonical abstraction with no unresolved calls;
- exact structural wiring is content-bound in v2 request/receipt provenance;
- old v1 modes retain established semantics and identities;
- static request identity is independent of ambient Cognitive Library state;
- library-bound source existence/arity checks occur only during synthesis;
- no shadow library or generated intermediate vocabulary exists;
- no lifecycle/Assurance authority is added;
- deterministic resource bounds are enforced;
- RED evidence proves new behavior was absent before production changes;
- focused and broad regressions pass on supported Python versions;
- final PR is non-draft, exact-head CI is green, merge uses expected-head guard, and post-merge `main` is verified content-equivalent to the tested feature tree.
