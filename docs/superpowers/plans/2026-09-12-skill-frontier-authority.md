# Neural R2.5 Skill Frontier Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every lineage-v2 request fail closed when its exact applicable skill set changes during inference, while exposing that same skill frontier through canonical context receipt provenance.

**Architecture:** Add one `skill-frontier` digest to the existing canonical context authority tuple rather than creating a parallel execution fence. `ContextCompiler` derives `applicable_skill_ids` and the digest from one immutable local snapshot; the already-integrated #374/#376 receipt/verifier/execution authority machinery then transports and revalidates it. The Memory/Context fallback path mirrors the same representation.

**Tech Stack:** Python 3.11/3.13, pytest, GitHub Actions, canonical SHA-style digesting via `nolane.core.canonical_digest`, existing Context/Memory/Execution control planes.

**Spec:** `docs/superpowers/specs/2026-09-12-skill-frontier-authority-design.md`

## Global Constraints

- Strict TDD: no production change before hosted RED is observed.
- No new `InferenceRequest`, execution-session, decision-receipt, skill-record, or frozen Neural R2.3 schema field.
- Use one exact skill snapshot to derive both `ContextCapsule.applicable_skill_ids` and `skill-frontier` during canonical compilation.
- `skill-frontier` is the digest of `{'skill_ids': list(exact_ordered_skill_ids)}` only; do not bind verifier evidence or unrelated skill metadata.
- Preserve all authority fences from #371–#376.
- Advance only component revisions required by executable version discipline, exactly +1 each.
- Merge only after exact-head direct gates and post-merge push workflows are green.

---

### Task 1: Prove the mid-inference skill revocation gap

**Files:**
- Modify: `tests/test_execution_post_inference_context_frontier_authority.py`

**Interfaces:**
- Consumes: `OrganizationRuntime.first_generation()`, public governed skill verification/promotion APIs, `SkillEvolutionEngine.quarantine(...)`, normal execution `start(...)`/`step(...)`.
- Produces: regression `test_skill_quarantine_during_inference_rejects_before_persistence`.

- [ ] **Step 1: Add a public governed PERSONAL-skill fixture**

Import `EvidenceRecord` and `SkillScope`. Add a test helper that:

```python
def _promoted_personal_skill(runtime: OrganizationRuntime, owner_agent_id: str):
    owner = runtime.registry.get(owner_agent_id)
    skill = runtime.evolution.propose(
        owner_agent_id=owner.agent_id,
        region=owner.region,
        name='request-bound-skill-frontier',
        body='a skill used by inference must remain authorized until its decision is persisted',
    )
    evidence = EvidenceRecord(
        'skill-frontier-independent-verification',
        'memory.worker',
        True,
        false_accepts=0,
        regressions=0,
    )
    authority = runtime.learning_substrate.learning_authority
    lease = authority.issue(
        subject_kind='skill',
        subject_id=skill.skill_id,
        operation_class='skill.verify',
        producer_agent_id=skill.owner_agent_id,
        evidence=evidence,
        subject_digest=runtime.evolution.verification_subject_digest(skill.skill_id),
    )
    runtime.evolution.verify(skill.skill_id, evidence, authority_lease_id=lease.lease_id)
    runtime.learning_substrate.record_skill_validation(
        skill.skill_id,
        regression_evidence_ids=('skill-frontier-regression-a', 'skill-frontier-regression-b'),
        causal_ablation_evidence_ids=('skill-frontier-causal-ablation',),
        regression_evidence_families={
            'skill-frontier-regression-a': 'skill-frontier-family-a',
            'skill-frontier-regression-b': 'skill-frontier-family-b',
        },
        causal_ablation_evidence_families={
            'skill-frontier-causal-ablation': 'skill-frontier-causal-family',
        },
    )
    return runtime.individual_evolution.promote_skill(skill.skill_id, SkillScope.PERSONAL)
```

If the runtime rejects `memory.worker` as the verifier for this exact owner, use the existing known independent verifier fixture from Memory Learning tests without weakening production policy.

- [ ] **Step 2: Add the decisive failing test**

Create a task leased to `memory.chief` and a normal repository workspace. Assert the promoted skill is initially returned by:

```python
runtime.evolution.skills_for('memory.chief', region='memory-context-knowledge')
```

Bind a backend whose `decide(...)` quarantines the exact skill and then returns a valid `ExecutionAction.wait(...)` decision. Call `runtime.execution.step(...)` inside:

```python
with pytest.raises(PermissionError, match='context.*authority|skill.*frontier|authority.*artifact'):
    runtime.execution.step(session.session_id)
```

Before the call, snapshot execution state/session/workspace digest. After rejection assert:

- the skill is quarantined and no longer applicable;
- execution state/session are byte-for-byte/equality unchanged;
- no decision/step/terminal receipt was persisted;
- task remains leased and incomplete;
- workspace digest/epoch ownership are unchanged.

- [ ] **Step 3: Commit test-only RED**

Commit only the test change with message:

```text
test(neural): reject stale decisions after skill quarantine
```

- [ ] **Step 4: Verify hosted RED**

Run the workflow that owns `tests/test_execution_post_inference_context_frontier_authority.py` on Python 3.11 and 3.13. Expected failure: the `pytest.raises(PermissionError)` block reports that no exception was raised, while existing neighboring context-authority regressions remain green. Do not write production code until this exact RED is observed.

---

### Task 2: Bind one canonical skill snapshot into context authority

**Files:**
- Modify: `nolane/external_core/context.py`
- Modify: `tests/test_coding_agi_context_intelligence.py`

**Interfaces:**
- Produces: `skill_frontier_digest(skill_ids: tuple[str, ...]) -> str`.
- Produces: private `ContextCompiler._request_authority_snapshot(...) -> tuple[tuple[tuple[str, Any], ...], tuple[str, ...]]` or equivalent single-read helper.
- Preserves: public `ContextCompiler.authoritative_artifacts(agent_id, task_id=None)` signature.

- [ ] **Step 1: Add focused frontier/atomicity tests before production**

In `tests/test_coding_agi_context_intelligence.py`, create a promoted applicable skill using the public governed path or a local canonical `SkillEvolutionEngine` fixture. Assert:

```python
compiled = runtime.memory_context.compile_context('memory.chief')
expected = canonical_digest({'skill_ids': list(compiled.capsule.applicable_skill_ids)})
frontier = dict(compiled.capsule.authoritative_artifacts)
receipt_frontier = dict(compiled.receipt.authoritative_frontier)
assert frontier['skill-frontier'] == expected
assert receipt_frontier['skill-frontier'] == expected
assert type(compiled.receipt).from_state(compiled.receipt.to_state()) == compiled.receipt
```

Add an atomicity variant that monkeypatches the underlying `evolution.skills_for` with a counting wrapper and asserts one canonical context compilation reads the skill set exactly once while `applicable_skill_ids` and `skill-frontier` remain aligned.

- [ ] **Step 2: Run focused tests and verify they are RED**

Run only the new tests. Expected current failure: `skill-frontier` is absent from capsule/receipt authority. The atomicity test must not fail due to fixture setup.

- [ ] **Step 3: Implement `skill_frontier_digest`**

At the top of `nolane/external_core/context.py`, import:

```python
from nolane.core.canonical_digest import canonical_digest
```

Add:

```python
def skill_frontier_digest(skill_ids: tuple[str, ...]) -> str:
    return canonical_digest({'skill_ids': list(skill_ids)})
```

Export it in `__all__`.

- [ ] **Step 4: Implement a single-read request authority snapshot**

Refactor only the existing authority construction. The helper must:

1. receive/resolve the `AgentIdentity` and effective task;
2. read `self.evolution.skills_for(...)` once when evolution exists;
3. build the existing master-plan/requirements/architecture/integration/regional rows unchanged;
4. append:

```python
('skill-frontier', skill_frontier_digest(skill_ids))
```

when evolution is configured;
5. return both `tuple(artifacts)` and the same `skill_ids` tuple.

`authoritative_artifacts(...)` returns only the artifact half. `compile(...)` calls the helper once and uses the returned `skill_ids` directly for `ContextCapsule.applicable_skill_ids`; remove the independent earlier `skills_for(...)` read.

- [ ] **Step 5: Run focused tests**

The new capsule/receipt and single-read tests must pass. Re-run the pre-existing full-authority tests from #374/#376 to ensure the new row is additive and exact.

- [ ] **Step 6: Commit minimal canonical GREEN**

Commit with message:

```text
fix(context): bind applicable skill frontier into request authority
```

---

### Task 3: Keep Memory/Context fallback provenance equivalent

**Files:**
- Modify: `nolane/memory/context_intelligence.py`
- Test: `tests/test_coding_agi_context_intelligence.py`

**Interfaces:**
- Consumes: `skill_frontier_digest(...)` from `nolane.external_core.context`.
- Produces: fallback capsule authority row identical in representation to canonical ContextCompiler.

- [ ] **Step 1: Add fallback RED**

Construct or use a `ContextIntelligenceCompiler` path without a bound base context but with one applicable skill. Compile a fallback capsule and assert:

```python
assert dict(result.capsule.authoritative_artifacts)['skill-frontier'] == canonical_digest(
    {'skill_ids': list(result.capsule.applicable_skill_ids)}
)
assert dict(result.receipt.authoritative_frontier)['skill-frontier'] == dict(
    result.capsule.authoritative_artifacts
)['skill-frontier']
```

Expected pre-change failure: missing `skill-frontier`.

- [ ] **Step 2: Implement fallback binding**

Import `skill_frontier_digest` beside `ContextCapsule`. In `_fallback_capsule(...)`, reuse the already-computed `skills` tuple and append exactly one authority row:

```python
('skill-frontier', skill_frontier_digest(skills))
```

Do not read `skills_for(...)` again.

- [ ] **Step 3: Run Part XI focused suite**

All context-intelligence tests, including full frontier, tamper, receipt round-trip, and fallback contracts, must pass.

- [ ] **Step 4: Commit fallback GREEN**

Commit with message:

```text
fix(memory): preserve skill frontier in fallback context provenance
```

---

### Task 4: Prove no overbinding

**Files:**
- Modify: `tests/test_coding_agi_context_intelligence.py`

**Interfaces:**
- Consumes: public `ContextCompiler.authoritative_artifacts` and governed skill verification APIs.
- Produces: regression that verifier-evidence changes alone do not change the skill authority digest.

- [ ] **Step 1: Add evidence-only stability test**

With one already-applicable skill, capture:

```python
before = dict(runtime.context.authoritative_artifacts(agent_id))['skill-frontier']
```

Add valid verification evidence to the same skill without changing its scope/quarantine/applicability, then capture `after`. Assert:

```python
assert before == after
assert tuple(row.skill_id for row in runtime.evolution.skills_for(agent_id, region=region)) == (skill.skill_id,)
```

- [ ] **Step 2: Run focused test**

Expected GREEN under the intended implementation because the digest binds exact applicable IDs only. If it fails, fix production to avoid digesting full mutable SkillRecord state; do not weaken the test.

- [ ] **Step 3: Commit regression**

Commit with message:

```text
test(context): keep skill authority scoped to applicability
```

---

### Task 5: Advance exact component revision projections

**Files:**
- Modify as required by `version_discipline_cli`, starting with:
  - `nolane/external_core/context.py`
  - `nolane/memory/context.py`
  - `nolane/metadata/component_versions.py`
  - `tests/test_refoundation_component_versions.py`
  - `tests/test_refoundation_memory_public_layout.py`
  - `tests/test_refoundation_wave5y_native_context.py`
- If and only if executable ownership analysis requires transitive revisions from `context_intelligence.py`, update the exact projection files it reports for `external.execution.control` and/or `external.integration`; preserve their independent public protocol/surface constants unless the gate proves a semantic surface migration.

**Interfaces:**
- `external.context` current revision/version: `4` / `0.0.4`.
- Target local context revision/version: `5` / `0.0.5`.

- [ ] **Step 1: Advance context owner**

Update canonical context implementation revision to 5 and both canonical/historical context component constants to `0.0.5`. Update the three known context projection tests to expect current `0.0.5` and next `0.0.6`.

- [ ] **Step 2: Run External Core version discipline**

Run the exact base→head discipline check. If it reports another affected owner due to the shared fallback helper, advance only that owner by exactly one and update every exact projection sentinel named by its contract tests.

- [ ] **Step 3: Re-run version discipline until clean**

Do not suppress or bypass the gate. Do not manufacture dependency bumps not reported by ownership analysis.

- [ ] **Step 4: Commit version projections**

Use a message describing the exact ownership result, for example:

```text
fix(metadata): advance context revision for skill frontier authority
```

If multiple transitive owners are required, mention them explicitly in the commit/PR evidence.

---

### Task 6: Exact-head verification and guarded integration

**Files:**
- No production changes unless a test exposes a real regression.
- Update PR body/issue comments with evidence.

**Interfaces:**
- Final candidate is one exact branch head SHA.

- [ ] **Step 1: Run exact-head direct gates**

Require fresh success on the final SHA for:

- Coding AGI Memory Context Intelligence Part XI — Python 3.11 + 3.13;
- External Core — Python 3.11 + 3.13 including version discipline/projection/coherence/admission;
- Memory Learning Substrate;
- Neural R2.4 Shared Core Acceptance;
- Neural R2.4 Runtime Cognition Activation;
- Neural R2.4 Execution Result Projection;
- Neural R2.4 Execution Decision Lineage;
- Refoundation E Acting Transactional Runtime;
- Nolane-AI Refoundation Epoch 0 — Python 3.11 + 3.13;
- R1.9 Integrity;
- R2.0i Integrity.

Historical R2.65/R2.66/R2.67.1 full-bundle failures may only be classified as baseline after comparison with unchanged `main`; they are not evidence for this change.

- [ ] **Step 2: Review final diff and concurrency state**

Verify no temporary workflow/patcher file remains, no unrelated protocol version changed, no unresolved review thread exists, and `main` has not advanced. If `main` advanced, recompute/rebase and rerun exact-head evidence.

- [ ] **Step 3: Mark PR ready and guarded-merge**

Update the PR body with RED and GREEN lineage. Merge only using the expected final head SHA.

- [ ] **Step 4: Verify merge lineage**

Fetch `main`; require the returned head to be the merge commit containing the exact verified candidate.

- [ ] **Step 5: Verify every triggered push workflow**

Enumerate workflows whose `head_sha` equals the merge commit. Require every actually triggered push workflow to finish `completed/success`, including matrix and dependent regression jobs.

- [ ] **Step 6: Close issue #377**

Add a closure comment recording the decisive RED, surviving H2 design, final merge SHA, component revision result, and post-merge evidence. Close as `completed` only after the post-merge checks are green.
