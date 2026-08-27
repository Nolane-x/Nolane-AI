# Refoundation Epoch 0 Wave 5M — Native Requirements Design

**Status:** Approved architectural continuation of the Refoundation Epoch 0 Authority Spine.

**Exact parent:** `69554e6cf963824e4ce7dd9034b168cecad6a1a3` (accepted Wave 5L)

## 1. Objective

Move executable and canonical write authority for `external.requirements` from the historical organization-era implementation at `cogcoder.organization.requirements` into `nolane.external_core.requirements` without changing observable behavior, persisted state semantics, authority boundaries, event semantics, digest semantics, or historical provenance.

This is a proof-carrying authority cutover, not a Requirements redesign.

## 2. Why Requirements is next

The Refoundation master architecture requires one explicit authority chain before deeper Planning, Architecture, Coding, and Execution cutovers. Requirements is the upstream semantic owner for accepted product constraints and acceptance criteria. Planning already consumes Requirements, and Architecture carries requirement references. Canonicalizing Requirements first therefore reduces dependency inversion and avoids moving Planning or Architecture while their upstream write authority still lives behind a compatibility facade.

The intended Authority Spine is:

`Requirements → Planning → Architecture → task/execution-facing domain systems`

Wave 5M covers only the first node.

## 3. Canonical and historical ownership

### Canonical implementation owner

`nolane/external_core/requirements.py`

After acceptance, public implementation classes and enums are defined by this module and report this module as their implementation owner.

### Historical compatibility/provenance path

`cogcoder/organization/requirements.py`

After cutover this path remains import-compatible and re-exports the exact canonical public objects. It no longer owns executable/write implementation authority.

No historical source is deleted or moved by this wave.

## 4. Component identity and versioning

Component: `external.requirements`

Version transition:

`0.0.0 → 0.0.1`

Only `external.requirements` advances because this is a component-local accepted revision. `external.planning`, `external.architecture`, `external.context`, and all unrelated components retain their current revisions.

The implementation-status ledger must change only this component from `COMPATIBILITY_FACADE` to `CANONICAL_NATIVE` and grant canonical write authority only through the canonical module.

The active facade binding for `external.requirements` must disappear once the historical path is an exact bridge to the native module.

## 5. Semantics that must remain exactly preserved

### 5.1 Requirement vocabulary

Preserve the exact string values and state interpretation of:

- `RequirementKind.FUNCTIONAL`
- `RequirementKind.NON_FUNCTIONAL`
- `RequirementKind.CONSTRAINT`
- `RequirementKind.SECURITY`
- `RequirementKind.COMPATIBILITY`
- `RequirementKind.QUALITY`
- `RequirementStatus.ACTIVE`
- `RequirementStatus.AMBIGUOUS`
- `RequirementStatus.SUPERSEDED`
- `RequirementStatus.REJECTED`

Enum names, serialized values, and round-trip behavior are compatibility contracts.

### 5.2 Acceptance criteria

`AcceptanceCriterion` retains:

- non-empty criterion id and statement validation;
- verification class;
- evidence expectations;
- stable `to_state` / `from_state` behavior.

### 5.3 Requirement nodes

`RequirementNode` retains:

- non-empty id/title/description validation;
- priority range `[0, 100]`;
- unique acceptance-criterion ids within a requirement;
- dependency references;
- acceptance criteria;
- status;
- stable state serialization.

### 5.4 Requirement graph

`RequirementGraph` retains:

- deterministic node ordering;
- rejection of unknown dependencies;
- rejection of dependency cycles;
- evidence-bearing mutations only;
- non-empty mutation batches;
- monotonic revision sequence;
- parent revision relation;
- changed-requirement tracking;
- canonical digest generation;
- state round-trip;
- rejection of non-canonical revision sequences;
- rejection of final graph-digest mismatch.

No second Requirements revision clock may be introduced.

### 5.5 Requirements control plane and authority

`RequirementsControlPlane` retains:

- source identity validation through the registry;
- canonical write authorization through the authority layer for accepted revisions;
- Requirements Chief routing for organization-changing events;
- evidence references on accepted changes;
- changed requirement object references;
- serialized control-plane state;
- exact restoration behavior.

No migration step may broaden who can write Requirements state.

### 5.6 Proposal semantics

Preserve:

- ambiguity proposals;
- change proposals;
- acceptance-gap proposals;
- source identity validation;
- target requirement existence validation;
- non-empty proposal text;
- event routing to `requirements.chief`;
- region `requirements-product`;
- object/evidence references;
- `requirements_action` payload distinctions.

The existing event aliases used to keep Part-I serialization stable remain behaviorally compatible. This wave does not redesign `EventKind`.

## 6. Dependency boundary

Allowed dependencies remain low-level shared schemas/digest/event/authority/registry contracts already used by Requirements.

This wave must not make Requirements depend on Planning, Architecture, Coding, UI/UX, Evaluation, or Execution implementations.

Planning may consume canonical Requirements in its own future cutover; Requirements must not depend back on Planning.

## 7. Explicit exclusions

Wave 5M does **not**:

- native-cutover `external.planning`;
- native-cutover `external.architecture`;
- reconcile TaskGraph plan/lease clocks;
- redesign organization events;
- alter the 67-identity organization;
- change Requirements business semantics;
- create a new requirements language/model;
- migrate historical files into archive;
- delete compatibility paths;
- change Neural Core;
- broaden any R-series or AGI/scientific claim.

## 8. TDD and parity strategy

RED contracts are written before production authority moves. They must demonstrate at least:

1. canonical Requirements symbols are currently aliases owned by the historical module;
2. after cutover canonical public implementation objects are defined under `nolane.external_core.requirements`;
3. the historical module re-exports the exact canonical objects;
4. enum/state serialization parity;
5. validation parity for malformed criteria/nodes;
6. unknown dependency rejection;
7. dependency-cycle rejection;
8. deterministic ordering/digest behavior;
9. evidence/reason/mutation requirements;
10. state round-trip and digest integrity;
11. authorized write behavior;
12. unauthorized write denial;
13. proposal event target/region/action/object/evidence behavior;
14. component revision `0.0.1` and native implementation ledger state;
15. removal from active facade bindings;
16. generated native debt transition `33 → 32`;
17. no temporary bootstrap/carrier mechanism remains at final head.

## 9. Migration bookkeeping

After implementation:

- `external.requirements` revision is 1;
- implementation status is `CANONICAL_NATIVE`;
- canonical module is `nolane.external_core.requirements`;
- legacy source/provenance is `cogcoder.organization.requirements`;
- canonical write authority is true only as a consequence of native ownership;
- active facade registry no longer lists `external.requirements`;
- generated native-debt state is refreshed by repository audit rather than manually authored;
- all neighboring facade sentinels remain locked.

## 10. Security / authority invariants

The migration must fail closed if:

- a non-authorized identity can directly mutate accepted Requirements state;
- evidence can be omitted from an accepted revision;
- requirement dependency cycles become possible;
- unknown dependencies become silently tolerated;
- proposal events can masquerade as accepted revisions;
- a historical bridge and canonical module become two independently mutable implementations;
- Planning or another component acquires Requirements write authority as a side effect.

## 11. Rollback

Rollback target is the exact accepted Wave 5L parent:

`69554e6cf963824e4ce7dd9034b168cecad6a1a3`

Because no historical source is deleted or moved, rollback can restore the compatibility-facade ownership model without reconstructing lost bytes. Any persisted Requirements state remains governed by parity-preserving serialization contracts.

## 12. Acceptance gate

Wave 5M is accepted only when the same exact post-cleanup head passes the hosted Refoundation workflow on Python 3.11 and 3.13, including:

- compile;
- 67-AI dossier freshness;
- repository audit freshness;
- all Refoundation contracts;
- zero-loss evidence generation/upload;
- all organization/campaign/execution regressions;
- frozen Neural R2.3 metadata contracts.

The generated debt must report 32 non-native component records with `external.requirements` absent from debt. No temporary bootstrap/carrier authority may remain. The PR may then become Ready for Review, but must not be auto-merged.
