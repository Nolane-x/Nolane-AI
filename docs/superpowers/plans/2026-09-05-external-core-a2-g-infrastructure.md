# External Core A2 + G Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade G (Artifacts, Operations, Research) into a provenance-closed, replayable, currentness-aware substrate and add an authority-neutral External Core Coherence Fabric that lets A–G interoperate through typed, digest-bound contracts without creating a new governor.

**Architecture:** Implement G first so the fabric is grounded in real authority-bearing consumers rather than abstract framework code. New modules are immutable/content-addressed wherever possible, restore paths recompute semantic validity, and the fabric may validate structure or compatibility but may not verify, assure, execute, promote, learn, release, or mutate another family’s canonical state.

**Tech Stack:** Python 3.11/3.13, dataclasses, Enum/IntEnum, canonical JSON/digests from `nolane.core.canonical_digest`, pytest, existing External Core/Assurance/organization registries, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-05-external-core-a2-g-infrastructure-design.md`

## Global Constraints

- `CURRENT/` remains the highest repository architecture authority.
- Nolane World 0.12.0 is design/research provenance only; no World runtime authority enters Nolane AI.
- ECF is not family H and is not a mutable governor.
- Proposal is not authority; evidence is not self-validating; historical green is not current validity.
- Restore/replay must reconstruct validity and authority from exact bindings rather than trusting serialized status labels.
- No hidden scalar confidence or quality score may override A-family categorical Truth/Assurance semantics.
- Existing A–F public contracts remain backward compatible unless an explicit versioned bridge is added.
- Legacy G `0.0.1` state remains readable; legacy records do not silently acquire v2 authority properties.
- All new IDs that claim content-addressed identity are recomputed on restore and fail closed on mismatch.
- Python `bool` must not be accepted where an integer epoch/budget/fence is semantically required.
- NaN/Infinity and non-canonical authority-significant payloads are rejected.

---

## File Structure

### New production modules

- `nolane/external_core/artifact_provenance.py` — artifact dependency DAG, revocation/supersession receipts, currentness assessment.
- `nolane/external_core/research_protocol.py` — research question certificate, hypothesis/rival/falsifier obligations, closure result.
- `nolane/external_core/research_budget.py` — finite category-partitioned research budget with append-only spend receipts.
- `nolane/external_core/research_trials.py` — append-only trial/result ledger preserving failed and negative trials.
- `nolane/external_core/operations_journal.py` — hash-chained G operational event journal.
- `nolane/external_core/operations_recovery.py` — snapshot, replay preflight, recovery certificate, exact/prefix/quarantine semantics.
- `nolane/external_core/component_contracts.py` — ExternalComponentManifest and contract/version declarations.
- `nolane/external_core/authority_graph.py` — machine-readable structural authority graph and composition validation.
- `nolane/external_core/handoff.py` — cross-family content-addressed handoff envelopes and consumer validation.
- `nolane/external_core/work_trace.py` — descriptive cross-family lineage graph.
- `nolane/external_core/capability_discovery.py` — read-only manifest/authority discovery.
- `nolane/external_core/coherence_audit.py` — deterministic structural audit and findings.
- `nolane/external_core/audit.py` — CLI for `python -m nolane.external_core.audit --check`.

### Existing production modules to extend narrowly

- `nolane/external_core/artifacts.py` — add v2 artifact envelope/store APIs while preserving `ArtifactRecord`/`ArtifactStore.put` compatibility.
- `nolane/external_core/research.py` — bind protocol/budget/trial/closure state and current handoff revalidation.
- `nolane/external_core/research_provenance.py` — expose exact currentness/status hooks without duplicating A Truth authority.
- `nolane/external_core/infrastructure_operations.py` — journal significant events and implement current release readiness.
- `nolane/external_core/operations.py` — compose new journal/recovery/current readiness without becoming release authority.
- `nolane/external_core/catalog.py` and/or `nolane/metadata/capabilities.py` — register read-only ECF discovery metadata only where existing patterns require it.
- `nolane/external_core/__init__.py` — public exports for stable A2 interfaces.
- `CURRENT/EXTERNAL_CORE.md` — record A2/G authority boundaries and version progression.

### Tests

- `tests/test_external_core_g1_artifact_integrity.py`
- `tests/test_external_core_g2_research_protocol.py`
- `tests/test_external_core_g3_operations_recovery.py`
- `tests/test_external_core_a2_component_contracts.py`
- `tests/test_external_core_a2_handoff_trace.py`
- `tests/test_external_core_a2_coherence_audit.py`
- `tests/test_external_core_a2_cross_family_matrix.py`

---

### Task 1: G1 Artifact Integrity and Provenance Closure

**Files:**
- Create: `nolane/external_core/artifact_provenance.py`
- Modify: `nolane/external_core/artifacts.py`
- Test: `tests/test_external_core_g1_artifact_integrity.py`

**Interfaces:**
- Consumes: `canonical_digest`, `canonical_json`, legacy `ArtifactRecord` and `ArtifactStore`.
- Produces: `ArtifactEnvelope`, `ArtifactCurrentness`, `ArtifactDependencyKind`, `ArtifactRevocationReceipt`, `ArtifactSupersessionReceipt`, `ArtifactProvenanceGraph`, `ArtifactStore.put_v2(...)`, `ArtifactStore.currentness(...)`.

- [ ] **Step 1: Write failing tests for v2 identity, restore integrity, DAG cycles, revocation closure, legacy compatibility and scalar-edge cases**

```python
import math
import pytest
from nolane.external_core.artifacts import ArtifactStore, ArtifactCurrentness


def test_v2_artifact_is_content_addressed_and_restore_recomputes_identity():
    store = ArtifactStore()
    row = store.put_v2(
        kind="research-synthesis",
        schema_version="2",
        producer_component_id="external.research",
        producer_agent_id="research.chief",
        content="payload",
        source_state_digest="s" * 64,
        evidence_refs=("e-1",),
        evidence_digests=("d" * 64,),
        dependency_artifact_ids=(),
        predecessor_artifact_ids=(),
        contract_id="g.research-synthesis",
        contract_version="2",
        created_epoch=3,
        currentness_max_age_epochs=5,
        metadata={"mode": "current_external"},
    )
    state = store.to_state()
    restored = ArtifactStore.from_state(state)
    assert restored.get_v2(row.artifact_id) == row
    state["artifact_envelopes"][0]["artifact_id"] = "artifact-forged"
    with pytest.raises(ValueError, match="artifact identity"):
        ArtifactStore.from_state(state)


def test_revoked_ancestor_invalidates_live_descendant_without_deleting_history():
    store = ArtifactStore()
    root = store.put_v2_minimal(kind="source", producer_component_id="external.research", producer_agent_id="research.chief", content="root")
    child = store.put_v2_minimal(kind="synthesis", producer_component_id="external.research", producer_agent_id="research.chief", content="child", dependency_artifact_ids=(root.artifact_id,))
    store.revoke_artifact(root.artifact_id, actor_component_id="external.artifacts", reason="source-retracted", evidence_refs=("e-revoke",))
    assert store.currentness(root.artifact_id).status is ArtifactCurrentness.REVOKED
    assert store.currentness(child.artifact_id).status is ArtifactCurrentness.DEPENDENCY_INVALID
    assert store.get_v2(child.artifact_id) == child


def test_artifact_dependency_cycle_is_rejected():
    store = ArtifactStore()
    a = store.put_v2_minimal(kind="a", producer_component_id="external.artifacts", producer_agent_id="infra.chief", content="a")
    with pytest.raises(ValueError, match="cycle"):
        store.provenance.bind_dependency(a.artifact_id, a.artifact_id)


def test_bool_epoch_and_non_finite_metadata_are_rejected():
    store = ArtifactStore()
    with pytest.raises((TypeError, ValueError)):
        store.put_v2_minimal(kind="x", producer_component_id="external.artifacts", producer_agent_id="infra.chief", content="x", created_epoch=True)
    with pytest.raises(ValueError):
        store.put_v2_minimal(kind="x", producer_component_id="external.artifacts", producer_agent_id="infra.chief", content="x", metadata={"score": math.nan})
```

- [ ] **Step 2: Run focused tests and confirm RED because v2 APIs do not exist**

Run: `python -m pytest -q tests/test_external_core_g1_artifact_integrity.py`
Expected: collection/import or attribute failures for the new interfaces while legacy artifact tests remain green.

- [ ] **Step 3: Implement immutable artifact envelope and provenance graph**

Core shape:

```python
class ArtifactCurrentness(str, Enum):
    CURRENT = "current"
    STALE = "stale"
    REVOKED = "revoked"
    DEPENDENCY_INVALID = "dependency_invalid"
    UNKNOWN = "unknown"

@dataclass(frozen=True, slots=True)
class ArtifactEnvelope:
    artifact_id: str
    digest: str
    kind: str
    schema_version: str
    producer_component_id: str
    producer_agent_id: str
    content: str
    content_digest: str
    source_state_digest: str
    evidence_refs: tuple[str, ...]
    evidence_digests: tuple[str, ...]
    dependency_artifact_ids: tuple[str, ...]
    predecessor_artifact_ids: tuple[str, ...]
    contract_id: str
    contract_version: str
    created_epoch: int
    currentness_max_age_epochs: int | None
    metadata_json: str
```

`artifact_id` must be derived from the semantic payload and checked again in `from_state`. `ArtifactProvenanceGraph` stores append-only revocation/supersession receipts and computes descendant invalidation recursively with cycle detection.

- [ ] **Step 4: Preserve legacy compatibility**

`ArtifactStore.put(...)`, `get(...)`, `records()` and existing serialized `artifacts` rows keep their old behavior. New state adds separate keys such as `artifact_envelopes`, `artifact_provenance`; absence of those keys restores as empty A2 state.

- [ ] **Step 5: Run G1 focused and existing artifact/operations/research regressions**

Run: `python -m pytest -q tests/test_external_core_g1_artifact_integrity.py tests/test_coding_agi_ops_*.py tests/test_coding_agi_research_*.py`
Expected: PASS.

- [ ] **Step 6: Commit G1**

```bash
git add nolane/external_core/artifacts.py nolane/external_core/artifact_provenance.py tests/test_external_core_g1_artifact_integrity.py
git commit -m "feat(external-core): harden artifact integrity and provenance"
```

---

### Task 2: G2 Research Protocol, Budget, Trial Ledger and Closure

**Files:**
- Create: `nolane/external_core/research_protocol.py`
- Create: `nolane/external_core/research_budget.py`
- Create: `nolane/external_core/research_trials.py`
- Modify: `nolane/external_core/research.py`
- Modify: `nolane/external_core/research_provenance.py`
- Test: `tests/test_external_core_g2_research_protocol.py`

**Interfaces:**
- Produces: `ResearchQuestionCertificate`, `ResearchHypothesis`, `ResearchBudget`, `ResearchBudgetReceipt`, `ResearchTrial`, `ResearchTrialLedger`, `ResearchClosureDisposition`, `ResearchClosureCertificate`.

- [ ] **Step 1: Write RED tests for rival-hypothesis obligations, finite budgets, negative trial retention, source independence and closure**

```python
def test_high_stakes_question_requires_rival_and_falsifier():
    with pytest.raises(ValueError, match="rival"):
        ResearchQuestionCertificate.create(
            question="Does candidate X improve recovery?",
            decision_ref="capability:X",
            scope="recovery",
            unknowns=("cross-platform behavior",),
            assumptions=("same toolchain",),
            hypotheses=(ResearchHypothesis("h1", "X helps", ("regression",)),),
            rival_hypotheses=(),
            falsifiers=(),
            closure_criteria=("independent reproduction",),
            source_constraints=("primary",),
            budget_class="high",
            high_stakes=True,
        )


def test_budget_cannot_overspend_or_use_bool_as_units():
    budget = ResearchBudget.create(total_units=20, explore=5, falsify=5, verify=5, replicate=3, integrate=2)
    budget = budget.spend(category="explore", units=5, reason="search", evidence_refs=("e1",))
    with pytest.raises(ValueError, match="budget"):
        budget.spend(category="explore", units=1, reason="extra", evidence_refs=("e2",))
    with pytest.raises(TypeError):
        budget.spend(category="verify", units=True, reason="bad", evidence_refs=("e3",))


def test_negative_trials_are_append_only_and_required_for_closure():
    ledger = ResearchTrialLedger()
    ledger.record(..., outcome="negative", evidence_refs=("e-neg",))
    closure = assess_research_closure(..., trial_ledger=ledger, required_trial_ids=("trial-neg",))
    assert "trial-neg" in closure.trial_ids
```

- [ ] **Step 2: Implement certificates as content-addressed immutable objects**

Question certificate IDs and hypothesis IDs are digest-derived. Restore recomputes them. High-stakes or high-uncertainty questions require at least one explicit rival and one falsifier. A certificate cannot claim truth, Assurance, or execution authorization.

- [ ] **Step 3: Implement finite partitioned budget**

Budget categories are exactly `explore`, `falsify`, `verify`, `replicate`, `integrate`. Total must equal category allocations, all units must be real non-negative integers excluding bool, and each spend appends a digest-bound receipt. Scores/allocations are scheduling-only.

- [ ] **Step 4: Implement append-only research trials**

A trial records protocol/question/hypothesis ids, producer, evidence, outcome category, limitations, source-state digest, and predecessor. No API deletes or rewrites a prior trial. Failed, negative, inconclusive and positive trials remain visible.

- [ ] **Step 5: Add closure assessment and current handoff revalidation to ResearchControlPlane**

Closure must return categorical `CLOSED`, `BLOCKED`, or `UNKNOWN`, with stable reasons. It checks certificate obligations, budget accounting, required trials, freshness, unresolved contradiction, evidence availability, independent verification where required, and artifact currentness when v2 artifacts are used. Existing `create_handoff` remains backward compatible; a new `assess_current_handoff` revalidates current source/artifact/Assurance state.

- [ ] **Step 6: Run G2 + prior Research/A/C regressions and commit**

Run: `python -m pytest -q tests/test_external_core_g2_research_protocol.py tests/test_coding_agi_research_*.py tests/test_coding_agi_assurance_*.py`
Expected: PASS.

Commit: `feat(external-core): add governed research protocol and closure`

---

### Task 3: G3 Operational Journal, Recovery and Current Readiness

**Files:**
- Create: `nolane/external_core/operations_journal.py`
- Create: `nolane/external_core/operations_recovery.py`
- Modify: `nolane/external_core/infrastructure_operations.py`
- Modify: `nolane/external_core/operations.py`
- Test: `tests/test_external_core_g3_operations_recovery.py`

**Interfaces:**
- Produces: `OperationsEvent`, `OperationsJournal`, `OperationsSnapshot`, `RecoveryMode`, `RecoveryCertificate`, `OperationalLease`, `CurrentReleaseReadinessReceipt`.

- [ ] **Step 1: RED tests for hash-chain tamper, exact/prefix restore, divergent quarantine, lease fencing and stale historical readiness**

```python
def test_operations_journal_restore_rejects_tampered_previous_digest():
    journal = OperationsJournal()
    journal.append(kind="build_registered", subject_id="b1", payload={"digest": "a"})
    journal.append(kind="release_registered", subject_id="r1", payload={"digest": "b"})
    state = journal.to_state()
    state["events"][1]["previous_digest"] = "forged"
    with pytest.raises(ValueError, match="journal"):
        OperationsJournal.from_state(state)


def test_divergent_snapshot_is_quarantined_not_silently_merged():
    certificate = recover_operations(snapshot=foreign_snapshot, journal=local_journal, ...)
    assert certificate.mode is RecoveryMode.QUARANTINED
    assert not certificate.authoritative


def test_current_release_readiness_rechecks_revoked_package():
    historical = infrastructure.assess_release("release-1")
    assert historical.ready
    artifacts.revoke_artifact(package.artifact_id, actor_component_id="external.artifacts", reason="bad package", evidence_refs=("e",))
    current = infrastructure.assess_current_release_readiness("release-1")
    assert current.disposition.value == "blocked"
```

- [ ] **Step 2: Implement append-only canonical journal**

Each event binds monotonic sequence, event kind, subject, canonical payload, previous event digest and resulting event digest. Restore replays and verifies exact chain, duplicate transition id rebinding is rejected.

- [ ] **Step 3: Implement snapshot/recovery certificates**

Snapshot binds component versions, journal root/head, artifact graph digest, authority graph digest if supplied, active operation ids, readiness state root, registry digest if supplied. Recovery modes: `EXACT`, `FAST_FORWARD`, `QUARANTINED`. Divergence never merges automatically.

- [ ] **Step 4: Implement narrow G operational lease**

Lease owns only G operational resources, with monotonic fence epoch, owner/resource/predecessor binding and terminal release receipt. It must not replace E workspace lease or F engineering claims.

- [ ] **Step 5: Upgrade observability/current release assessment without rewriting legacy receipt semantics**

Add v2/current assessment path that checks package/rollback artifact currentness, reproducibility basis, observability currentness/coverage, reliability evidence, current Assurance disposition and version/baseline drift. Missing current evidence yields `UNKNOWN`, not historical READY.

- [ ] **Step 6: Run G3 regressions and commit**

Run: `python -m pytest -q tests/test_external_core_g3_operations_recovery.py tests/test_coding_agi_ops_*.py tests/test_coding_agi_assurance_*.py`
Expected: PASS.

Commit: `feat(external-core): add operational journal recovery and current readiness`

---

### Task 4: A2 Component Contracts and Structural Authority Graph

**Files:**
- Create: `nolane/external_core/component_contracts.py`
- Create: `nolane/external_core/authority_graph.py`
- Test: `tests/test_external_core_a2_component_contracts.py`

**Interfaces:**
- Produces: `ExternalCoreFamily`, `AuthorityCapability`, `ExternalComponentManifest`, `AuthorityRelation`, `AuthorityEdge`, `ExternalAuthorityGraph`, `AuthorityGraphFinding`.

- [ ] **Step 1: RED tests for manifest digest, forbidden authority, duplicate writer, version incompatibility and mutable cycles**

```python
def test_candidate_synthesis_manifest_cannot_claim_promote_authority():
    with pytest.raises(ValueError, match="forbidden"):
        manifest("external.candidate_synthesis", family="C", authority_capabilities=("promote",), forbidden_authorities=("promote",))


def test_duplicate_canonical_writer_is_rejected():
    graph = ExternalAuthorityGraph((manifest_a, manifest_b))
    with pytest.raises(ValueError, match="writer"):
        graph.validate()


def test_descriptive_trace_cannot_become_authority_transitively():
    graph.add_edge(AuthorityEdge("external.work_trace", "external.assurance", AuthorityRelation.AUTHORIZES_INPUT_TO))
    assert any(f.code == "DESCRIPTIVE_AUTHORITY_ESCALATION" for f in graph.findings())
```

- [ ] **Step 2: Implement manifest canonicalization and version-range overlap**

Manifests are immutable, self-digesting and reject duplicate entries, invalid family, overlapping `authority_capabilities`/`forbidden_authorities`, non-canonical numeric values, or malformed compatibility ranges.

- [ ] **Step 3: Implement graph validator**

Reject duplicate mutable-resource writers, authority-escalating cycles, self-verification/self-Assurance loops when the relation requires independence, descriptive-to-authoritative escalation, incompatible producer/consumer protocol ranges and forbidden authority reached transitively.

- [ ] **Step 4: Seed manifests only for components needed by A2 tests**

Do not hand-author all ~External Core modules in one patch. Provide a deterministic registry API and seed the G + key A/C/D/E/F components used by the cross-family matrix; expand manifests incrementally through explicit registrations.

- [ ] **Step 5: Run and commit**

Run: `python -m pytest -q tests/test_external_core_a2_component_contracts.py`
Expected: PASS.

Commit: `feat(external-core): add component contracts and authority graph`

---

### Task 5: Cross-Family Handoff Envelope and Cognitive Work Trace

**Files:**
- Create: `nolane/external_core/handoff.py`
- Create: `nolane/external_core/work_trace.py`
- Test: `tests/test_external_core_a2_handoff_trace.py`

**Interfaces:**
- Produces: `HandoffAuthorityClass`, `FreshnessFence`, `ExternalHandoffEnvelope`, `HandoffValidationResult`, `CognitiveWorkTrace`, `WorkTraceNode`, `WorkTraceEdge`.

- [ ] **Step 1: RED tests for forged digest, producer version drift, stale fence, predecessor mismatch and trace non-authority**

```python
def test_handoff_restore_recomputes_content_addressed_id():
    envelope = ExternalHandoffEnvelope.create(...)
    state = envelope.to_state()
    state["handoff_id"] = "forged"
    with pytest.raises(ValueError, match="handoff identity"):
        ExternalHandoffEnvelope.from_state(state)


def test_consumer_rejects_stale_source_state_even_when_historical_envelope_was_valid():
    result = validate_handoff(envelope, manifests=manifests, current_source_state_digest="new")
    assert not result.valid
    assert "SOURCE_STATE_DRIFT" in result.reason_codes


def test_work_trace_has_no_authority_upgrade_api():
    trace = CognitiveWorkTrace()
    trace.append(...)
    assert not hasattr(trace, "authorize")
    assert not hasattr(trace, "promote")
```

- [ ] **Step 2: Implement envelope create/restore/consumer validation**

Envelope binds exact producer/consumer ids and versions, subject digest, contract, authority class, source state, evidence/artifact refs and digests, predecessor handoffs, freshness fence, limitations/known unknowns and payload/envelope digests. Consumer validation checks everything it can resolve; missing required current binding returns invalid/UNKNOWN rather than assuming validity.

- [ ] **Step 3: Implement descriptive trace DAG**

Trace supports forks, aborted/negative paths, supersession and missing-link diagnostics. It is immutable-by-append and never returns authorization/Assurance/verification decisions.

- [ ] **Step 4: Run and commit**

Run: `python -m pytest -q tests/test_external_core_a2_handoff_trace.py`
Expected: PASS.

Commit: `feat(external-core): add typed handoffs and cognitive work trace`

---

### Task 6: Capability Discovery, Restore Preflight and Coherence Audit

**Files:**
- Create: `nolane/external_core/capability_discovery.py`
- Create: `nolane/external_core/coherence_audit.py`
- Create: `nolane/external_core/audit.py`
- Modify: `nolane/external_core/catalog.py`
- Test: `tests/test_external_core_a2_coherence_audit.py`

**Interfaces:**
- Produces: `CapabilityDescriptor`, `CapabilityDiscovery`, `CoherenceFinding`, `CoherenceReport`, `RestorePreflightResult`, `audit_external_core(...)`.

- [ ] **Step 1: RED tests for undeclared dependencies, orphan handoffs, revoked live descendants, protocol drift, mutable cycles and restore drift**

```python
def test_audit_reports_forbidden_cross_family_authority_and_orphan_handoff():
    report = audit_external_core(manifests=(...), authority_graph=graph, handoffs=(orphan,), artifacts=store)
    assert {f.code for f in report.findings} >= {"FORBIDDEN_AUTHORITY_COMPOSITION", "ORPHAN_HANDOFF"}
    assert not report.clean


def test_restore_preflight_fails_closed_on_registry_or_graph_digest_drift():
    result = preflight_restore(snapshot, current_registry_digest="different", current_authority_graph_digest="different")
    assert not result.accepted
```

- [ ] **Step 2: Implement read-only capability discovery**

Query by contract kind or component and return exact manifest/version/evidence prerequisites/authority class/recovery semantics/current availability. No invocation path is exposed.

- [ ] **Step 3: Implement deterministic audit findings**

Stable code + severity + component/subject refs + evidence refs. Sort findings deterministically. Audit covers the 15 design categories and never claims task correctness.

- [ ] **Step 4: Add CLI**

`python -m nolane.external_core.audit --check` returns exit 0 only when structural report is clean. `--json` prints canonical machine-readable report. No write/mutation mode is added in A2.

- [ ] **Step 5: Run and commit**

Run: `python -m pytest -q tests/test_external_core_a2_coherence_audit.py`
Expected: PASS.

Commit: `feat(external-core): add capability discovery and coherence audit`

---

### Task 7: Cross-Family Contract Matrix and Public Integration

**Files:**
- Modify: `nolane/external_core/__init__.py`
- Modify: `nolane/external_core/catalog.py` or `nolane/metadata/capabilities.py` only as required by the existing canonical registry pattern.
- Modify: `CURRENT/EXTERNAL_CORE.md`
- Test: `tests/test_external_core_a2_cross_family_matrix.py`

**Interfaces:**
- Validates paths: `A→C`, `C→D`, `D→E`, `E→F`, `F→A`, `A→B`, `B→C`, `C→G` and at least one full-loop lineage.

- [ ] **Step 1: Write adversarial cross-family tests**

Cover tampered digest, stale evidence, schema downgrade, producer component upgrade mid-handoff, registry drift, source-state drift, bool-as-int, NaN, partial snapshot, crash/replay fork, duplicate writer and self-verification laundering.

- [ ] **Step 2: Register stable public interfaces without broad wildcard authority**

Exports expose datatypes/validators. Existing component ownership stays unchanged. Catalog additions describe capability; they do not change execution permissions.

- [ ] **Step 3: Update CURRENT authority document**

Document G version progression and ECF’s non-governor boundary. State explicitly that a clean ECF audit proves structural coherence only.

- [ ] **Step 4: Run matrix plus Refoundation regressions**

Run: `python -m pytest -q tests/test_external_core_a2_*.py tests/test_external_core_g*.py`
Then run the repository’s authoritative Refoundation/organization suites as configured in `.github/workflows` for Python 3.11 and 3.13.

- [ ] **Step 5: Commit integration**

Commit: `feat(external-core): integrate A2 coherence fabric across A-G`

---

### Task 8: Hosted Verification, Review and PR Closure

**Files:**
- Modify/add one dedicated A2 workflow only if existing Refoundation workflow path filters do not run on the new files.
- Update PR #337 body with exact test evidence.

- [ ] **Step 1: Push complete branch and inspect PR-triggered workflow runs for exact head SHA**

Require both Python 3.11 and 3.13 where the repository’s acceptance policy already requires them.

- [ ] **Step 2: If a failure occurs, use systematic debugging before changing code**

Classify failure as A2 defect, pre-existing unrelated failure, workflow path-filter omission or environment-specific issue. Do not weaken tests to force green.

- [ ] **Step 3: Run verification-before-completion checks**

Required evidence before completion claim:

- focused G1/G2/G3 tests green;
- A2 component/handoff/audit/cross-family tests green;
- prior G Operations/Research regressions green;
- Refoundation authoritative gate green on exact PR head or explicit documented unrelated blocker;
- `python -m nolane.external_core.audit --check` clean on test fixture/current declarations;
- no TODO/TBD placeholders in spec/plan/new production modules;
- PR diff contains no accidental authority relocation from A–F to ECF/G.

- [ ] **Step 4: Mark PR ready for review only after evidence is attached**

Do not auto-merge unless the user explicitly requests merging or the repository’s existing workflow clearly establishes that this branch is intended to merge automatically.
