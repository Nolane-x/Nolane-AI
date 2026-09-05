# External Core A2 + G Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade G (Artifacts, Operations, Research) into a provenance-closed, replayable, currentness-aware substrate and add an authority-neutral External Core Coherence Fabric (ECF) for typed, digest-bound A–G interoperability.

**Architecture:** Implement G first, then the shared fabric. All new authority-significant state is immutable/content-addressed or append-only; restore recomputes validity; ECF validates structure/compatibility but never verifies, Assures, executes, promotes, learns, releases, or mutates another family’s canonical state.

**Tech Stack:** Python 3.11/3.13, dataclasses, Enum/IntEnum, `nolane.core.canonical_digest`, pytest, existing External Core/Assurance/organization authorities, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-05-external-core-a2-g-infrastructure-design.md`

## Global Constraints

- `CURRENT/` remains highest repository architecture authority.
- Nolane World 0.12.0 is design provenance only; it gains no Nolane AI runtime authority.
- ECF is neither family H nor a governor.
- Proposal != authority; evidence != self-validation; historical green != current validity.
- Restore/replay reconstructs validity from exact bindings and never trusts serialized status labels alone.
- No scalar confidence may override A-family categorical Truth/Assurance semantics.
- Existing A–F public contracts remain compatible unless an explicit versioned bridge is added.
- Legacy G `0.0.1` state remains readable and does not silently gain A2 authority properties.
- Content-addressed IDs are recomputed on restore and mismatches fail closed.
- `bool` is rejected where epoch/budget/fence requires an integer.
- NaN/Infinity and non-canonical authority-significant values are rejected.

## File Map

New production modules:
- `artifact_provenance.py`: artifact DAG, revocation, supersession, currentness.
- `research_protocol.py`: research question/hypothesis/closure contracts.
- `research_budget.py`: finite partitioned research budget and spend receipts.
- `research_trials.py`: append-only positive/negative/failed/inconclusive trial ledger.
- `operations_journal.py`: hash-chained operational events.
- `operations_recovery.py`: snapshots, recovery certificates, lease/fence.
- `component_contracts.py`: component manifests and protocol declarations.
- `authority_graph.py`: structural authority composition validator.
- `handoff.py`: cross-family handoff envelope and consumer validation.
- `work_trace.py`: descriptive cross-family lineage DAG.
- `capability_discovery.py`: read-only capability introspection.
- `coherence_audit.py`: deterministic structural audit.
- `audit.py`: `python -m nolane.external_core.audit --check` CLI.

Existing modules changed narrowly:
- `artifacts.py`, `research.py`, `research_provenance.py`, `infrastructure_operations.py`, `operations.py`, `catalog.py` or its canonical metadata implementation, `__init__.py`, `CURRENT/EXTERNAL_CORE.md`.

New tests:
- `tests/test_external_core_g1_artifact_integrity.py`
- `tests/test_external_core_g2_research_protocol.py`
- `tests/test_external_core_g3_operations_recovery.py`
- `tests/test_external_core_a2_component_contracts.py`
- `tests/test_external_core_a2_handoff_trace.py`
- `tests/test_external_core_a2_coherence_audit.py`
- `tests/test_external_core_a2_cross_family_matrix.py`

---

### Task 1: G1 Artifact Integrity and Provenance Closure

**Files:** create `artifact_provenance.py`; modify `artifacts.py`; test `test_external_core_g1_artifact_integrity.py`.

**Produces:** `ArtifactEnvelope`, `ArtifactCurrentness`, `ArtifactRevocationReceipt`, `ArtifactSupersessionReceipt`, `ArtifactProvenanceGraph`, `ArtifactStore.put_v2`, `get_v2`, `revoke_artifact`, `currentness`.

- [ ] **Step 1: Write RED tests**

```python
import math
import pytest
from nolane.external_core.artifacts import ArtifactCurrentness, ArtifactStore


def _put(store, content, deps=()):
    return store.put_v2(
        kind="research-synthesis",
        schema_version="2",
        producer_component_id="external.research",
        producer_agent_id="research.chief",
        content=content,
        source_state_digest="s" * 64,
        evidence_refs=("e-1",),
        evidence_digests=("d" * 64,),
        dependency_artifact_ids=deps,
        predecessor_artifact_ids=(),
        contract_id="g.research-synthesis",
        contract_version="2",
        created_epoch=3,
        currentness_max_age_epochs=5,
        metadata={"mode": "current_external"},
    )


def test_restore_recomputes_v2_artifact_identity():
    store = ArtifactStore()
    row = _put(store, "payload")
    state = store.to_state()
    assert ArtifactStore.from_state(state).get_v2(row.artifact_id) == row
    state["artifact_envelopes"][0]["artifact_id"] = "artifact-forged"
    with pytest.raises(ValueError, match="artifact identity"):
        ArtifactStore.from_state(state)


def test_revoked_ancestor_invalidates_descendant_without_deletion():
    store = ArtifactStore()
    root = _put(store, "root")
    child = _put(store, "child", (root.artifact_id,))
    store.revoke_artifact(root.artifact_id, actor_component_id="external.artifacts", reason="retracted", evidence_refs=("e-r",))
    assert store.currentness(root.artifact_id).status is ArtifactCurrentness.REVOKED
    assert store.currentness(child.artifact_id).status is ArtifactCurrentness.DEPENDENCY_INVALID
    assert store.get_v2(child.artifact_id) == child


def test_cycle_bool_epoch_and_nan_fail_closed():
    store = ArtifactStore()
    root = _put(store, "root")
    with pytest.raises(ValueError, match="cycle"):
        store.provenance.bind_dependency(root.artifact_id, root.artifact_id)
    with pytest.raises(TypeError):
        store.put_v2(kind="x", schema_version="2", producer_component_id="external.artifacts", producer_agent_id="infra.chief", content="x", source_state_digest="s", evidence_refs=("e",), evidence_digests=("d",), dependency_artifact_ids=(), predecessor_artifact_ids=(), contract_id="x", contract_version="2", created_epoch=True, currentness_max_age_epochs=None, metadata={})
    with pytest.raises(ValueError):
        store.put_v2(kind="x", schema_version="2", producer_component_id="external.artifacts", producer_agent_id="infra.chief", content="x", source_state_digest="s", evidence_refs=("e",), evidence_digests=("d",), dependency_artifact_ids=(), predecessor_artifact_ids=(), contract_id="x", contract_version="2", created_epoch=1, currentness_max_age_epochs=None, metadata={"score": math.nan})
```

- [ ] **Step 2:** Run `python -m pytest -q tests/test_external_core_g1_artifact_integrity.py`; confirm RED because the A2 interfaces do not exist.
- [ ] **Step 3:** Implement immutable v2 envelopes, exact restore identity checks, acyclic dependency graph, append-only revocation/supersession receipts, descendant invalidation, categorical currentness.
- [ ] **Step 4:** Keep legacy `ArtifactStore.put/get/records` and old `artifacts` state byte-compatible in semantics; missing A2 keys restore to empty A2 state.
- [ ] **Step 5:** Run focused + prior Operations/Research tests.
- [ ] **Step 6:** Commit `feat(external-core): harden artifact integrity and provenance`.

---

### Task 2: G2 Research Protocol, Budget, Trials and Closure

**Files:** create `research_protocol.py`, `research_budget.py`, `research_trials.py`; modify `research.py`, `research_provenance.py`; test `test_external_core_g2_research_protocol.py`.

**Produces:** `ResearchHypothesis`, `ResearchQuestionCertificate`, `ResearchBudget`, `ResearchBudgetReceipt`, `ResearchTrial`, `ResearchTrialLedger`, `ResearchClosureDisposition`, `ResearchClosureCertificate`.

- [ ] **Step 1: Write RED tests**

```python
import pytest
from nolane.external_core.research_budget import ResearchBudget
from nolane.external_core.research_protocol import ResearchHypothesis, ResearchQuestionCertificate
from nolane.external_core.research_trials import ResearchTrialLedger


def test_high_stakes_question_requires_rival_and_falsifier():
    h1 = ResearchHypothesis.create(statement="X helps", predicted_observations=("lower failures",))
    with pytest.raises(ValueError, match="rival"):
        ResearchQuestionCertificate.create(
            question="Does X improve recovery?", decision_ref="capability:X", scope="recovery",
            unknowns=("cross-platform",), assumptions=("same toolchain",), hypotheses=(h1,),
            rival_hypothesis_ids=(), falsifiers=(), closure_criteria=("independent reproduction",),
            source_constraints=("primary",), budget_class="high", high_stakes=True,
        )


def test_budget_is_partitioned_finite_and_bool_safe():
    budget = ResearchBudget.create(total_units=20, allocations={"explore": 5, "falsify": 5, "verify": 5, "replicate": 3, "integrate": 2})
    budget.spend(category="explore", units=5, reason="search", evidence_refs=("e1",))
    with pytest.raises(ValueError, match="budget"):
        budget.spend(category="explore", units=1, reason="overspend", evidence_refs=("e2",))
    with pytest.raises(TypeError):
        budget.spend(category="verify", units=True, reason="invalid", evidence_refs=("e3",))


def test_negative_trial_is_retained_after_restore():
    ledger = ResearchTrialLedger()
    trial = ledger.record(
        question_id="rq-1", hypothesis_id="h-1", producer_agent_id="research.chief",
        protocol_digest="p" * 64, source_state_digest="s" * 64, outcome="negative",
        observation="candidate regressed", limitations=("single platform",), evidence_refs=("e-neg",),
    )
    restored = ResearchTrialLedger.from_state(ledger.to_state())
    assert restored.get(trial.trial_id).outcome.value == "negative"
```

- [ ] **Step 2:** Implement content-addressed hypotheses/questions; high-stakes questions require explicit rival hypotheses and falsifiers. Certificates are descriptive only.
- [ ] **Step 3:** Implement exactly five budget categories: explore/falsify/verify/replicate/integrate; allocations sum exactly to total; append-only spend receipts; no epistemic-confidence semantics.
- [ ] **Step 4:** Implement append-only trial ledger preserving positive, negative, failed and inconclusive outcomes; restore recomputes IDs/digests.
- [ ] **Step 5:** Add closure assessment with `CLOSED/BLOCKED/UNKNOWN` and stable reasons; add `ResearchControlPlane.assess_current_handoff` that revalidates source freshness, artifact currentness and Assurance rather than trusting historical handoff status.
- [ ] **Step 6:** Run focused + prior Research/Assurance regressions; commit `feat(external-core): add governed research protocol and closure`.

---

### Task 3: G3 Operations Journal, Recovery and Current Readiness

**Files:** create `operations_journal.py`, `operations_recovery.py`; modify `infrastructure_operations.py`, `operations.py`; test `test_external_core_g3_operations_recovery.py`.

**Produces:** `OperationsEvent`, `OperationsJournal`, `OperationsSnapshot`, `RecoveryMode`, `RecoveryCertificate`, `OperationalLease`, `CurrentReleaseReadinessReceipt`.

- [ ] **Step 1: Write RED tests**

```python
import pytest
from nolane.external_core.operations_journal import OperationsJournal
from nolane.external_core.operations_recovery import OperationsSnapshot, RecoveryMode, recover_operations


def test_journal_restore_rejects_tampered_chain():
    journal = OperationsJournal()
    journal.append(kind="build_registered", subject_id="b1", payload={"digest": "a"})
    journal.append(kind="release_registered", subject_id="r1", payload={"digest": "b"})
    state = journal.to_state()
    state["events"][1]["previous_digest"] = "forged"
    with pytest.raises(ValueError, match="journal"):
        OperationsJournal.from_state(state)


def test_divergent_snapshot_is_quarantined():
    journal = OperationsJournal()
    journal.append(kind="build_registered", subject_id="b1", payload={"digest": "a"})
    snapshot = OperationsSnapshot.create(component_versions={"external.operations": "0.1.0"}, journal_head_digest="foreign", journal_length=1, artifact_graph_digest="a", authority_graph_digest="g", readiness_state_digest="r", registry_digest="x", active_operation_ids=())
    result = recover_operations(snapshot=snapshot, journal=journal, current_artifact_graph_digest="a", current_authority_graph_digest="g", current_readiness_state_digest="r", current_registry_digest="x")
    assert result.mode is RecoveryMode.QUARANTINED
    assert not result.authoritative
```

- [ ] **Step 2:** Implement append-only journal with monotonic sequence, previous digest and canonical event digest; restore verifies entire chain.
- [ ] **Step 3:** Implement snapshots and recovery modes `EXACT`, `FAST_FORWARD`, `QUARANTINED`; divergent histories never auto-merge.
- [ ] **Step 4:** Implement G-only operational lease/fence with monotonic fence epoch; it must not replace E workspace leases or F claim leases.
- [ ] **Step 5:** Add current release-readiness assessment that rechecks package/rollback artifact currentness, reproduction basis, observability, reliability evidence, current Assurance and baseline/version drift. Missing current evidence -> `UNKNOWN`.
- [ ] **Step 6:** Run focused + prior Ops/Assurance regressions; commit `feat(external-core): add operational journal recovery and current readiness`.

---

### Task 4: Component Contracts and Authority Graph

**Files:** create `component_contracts.py`, `authority_graph.py`; test `test_external_core_a2_component_contracts.py`.

- [ ] **Step 1: Write RED tests**

```python
import pytest
from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily
from nolane.external_core.authority_graph import ExternalAuthorityGraph


def test_manifest_rejects_capability_also_declared_forbidden():
    with pytest.raises(ValueError, match="forbidden"):
        ExternalComponentManifest.create(component_id="external.candidate_synthesis", component_version="0.0.4", family=ExternalCoreFamily.C, protocol_versions={"candidate": "4"}, consumes_contracts=(), produces_contracts=("candidate",), authority_capabilities=("promote",), forbidden_authorities=("promote",), mutable_resources=(), evidence_inputs=("discovery",), evidence_outputs=("candidate",), restore_protocol="exact", compatibility_floor="0.0.4", compatibility_ceiling="0.0.4")


def test_duplicate_mutable_writer_is_rejected():
    a = ExternalComponentManifest.minimal("external.a", ExternalCoreFamily.A, mutable_resources=("resource:x",))
    b = ExternalComponentManifest.minimal("external.b", ExternalCoreFamily.B, mutable_resources=("resource:x",))
    with pytest.raises(ValueError, match="writer"):
        ExternalAuthorityGraph((a, b), ()).validate()
```

- [ ] **Step 2:** Implement immutable self-digesting manifests, normalized unique tuple fields and compatibility ranges.
- [ ] **Step 3:** Implement graph checks for duplicate writers, authority-escalating cycles, self-verification/self-Assurance, descriptive-to-authoritative escalation, incompatible protocols and transitive forbidden authority.
- [ ] **Step 4:** Seed only G plus key A/C/D/E/F components needed by the cross-family matrix; no giant hand-authored manifest migration in one patch.
- [ ] **Step 5:** Run focused tests; commit `feat(external-core): add component contracts and authority graph`.

---

### Task 5: Typed Handoffs and Cognitive Work Trace

**Files:** create `handoff.py`, `work_trace.py`; test `test_external_core_a2_handoff_trace.py`.

- [ ] **Step 1: Write RED tests**

```python
import pytest
from nolane.external_core.handoff import ExternalHandoffEnvelope, HandoffAuthorityClass
from nolane.external_core.work_trace import CognitiveWorkTrace


def test_handoff_restore_recomputes_identity():
    envelope = ExternalHandoffEnvelope.create(producer_component_id="external.research", producer_component_version="0.1.0", producer_agent_id="research.chief", consumer_component_id="external.planning", consumer_contract_range="1", subject_id="s1", subject_digest="d" * 64, contract_kind="research-input", contract_version="1", authority_class=HandoffAuthorityClass.INFORMATIVE, source_state_digest="s" * 64, predecessor_handoff_ids=(), evidence_bindings=(("e1", "e" * 64),), artifact_bindings=(), freshness_fence=None, limitations=("single source",), known_unknowns=("replication",), payload={"finding": "x"})
    state = envelope.to_state()
    state["handoff_id"] = "forged"
    with pytest.raises(ValueError, match="handoff identity"):
        ExternalHandoffEnvelope.from_state(state)


def test_trace_has_no_authority_upgrade_methods():
    trace = CognitiveWorkTrace(trace_id="trace-1")
    trace.append_node(component_id="external.research", subject_id="s1", subject_digest="d" * 64, status="informative", predecessor_node_ids=())
    assert not hasattr(trace, "authorize")
    assert not hasattr(trace, "promote")
```

- [ ] **Step 2:** Implement handoff envelope with producer/consumer versions, subject/contract, authority class, source-state digest, evidence/artifact digest bindings, predecessor IDs, optional freshness fence, limitations/unknowns, payload digest and envelope digest.
- [ ] **Step 3:** Consumer validation rechecks manifest compatibility, source-state/current bindings and predecessor existence; missing current proof fails closed.
- [ ] **Step 4:** Implement descriptive append-only trace DAG with forks, negative/aborted nodes, supersession and missing-link diagnostics; no authority APIs.
- [ ] **Step 5:** Run focused tests; commit `feat(external-core): add typed handoffs and cognitive work trace`.

---

### Task 6: Capability Discovery, Restore Preflight and Coherence Audit

**Files:** create `capability_discovery.py`, `coherence_audit.py`, `audit.py`; modify canonical catalog bridge only as needed; test `test_external_core_a2_coherence_audit.py`.

- [ ] **Step 1: Write RED tests**

```python
from nolane.external_core.coherence_audit import audit_external_core, preflight_restore


def test_audit_detects_orphan_handoff_and_duplicate_writer(store, manifests, graph, orphan_handoff):
    report = audit_external_core(manifests=manifests, authority_graph=graph, handoffs=(orphan_handoff,), artifact_store=store)
    codes = {finding.code for finding in report.findings}
    assert "ORPHAN_HANDOFF" in codes
    assert not report.clean


def test_restore_preflight_rejects_registry_and_graph_drift(snapshot):
    result = preflight_restore(snapshot=snapshot, current_registry_digest="registry-new", current_authority_graph_digest="graph-new", current_component_versions={"external.operations": "0.1.0"})
    assert not result.accepted
    assert "REGISTRY_DIGEST_DRIFT" in result.reason_codes
```

- [ ] **Step 2:** Implement read-only discovery by contract/component returning manifest version, evidence prerequisites, allowed authority class, recovery semantics and availability; expose no invoke method.
- [ ] **Step 3:** Implement deterministic audit findings for manifest validity, duplicate authority, forbidden composition, protocol drift, undeclared dependency, orphan/stale handoff, provenance cycle, revoked-live descendant, stale evidence, missing restore coverage, duplicate semantic authority, self-verification, mutable cycles, missing negative lineage, serialized-version drift.
- [ ] **Step 4:** Implement `python -m nolane.external_core.audit --check` and `--json`; A2 has no write mode.
- [ ] **Step 5:** Run focused tests; commit `feat(external-core): add capability discovery and coherence audit`.

---

### Task 7: Cross-Family Matrix and Public Integration

**Files:** modify `__init__.py`, canonical catalog metadata only as needed, `CURRENT/EXTERNAL_CORE.md`; test `test_external_core_a2_cross_family_matrix.py`.

- [ ] **Step 1:** Add adversarial paths `A->C`, `C->D`, `D->E`, `E->F`, `F->A`, `A->B`, `B->C`, `C->G` plus a full-loop trace; test tampered digest, stale evidence, schema downgrade, producer upgrade mid-handoff, registry drift, source-state drift, bool-as-int, NaN, partial snapshot, replay fork, duplicate writer and self-verification laundering.
- [ ] **Step 2:** Export stable A2 datatypes/validators without broad wildcard authority; metadata describes capabilities but changes no execution permissions.
- [ ] **Step 3:** Update `CURRENT/EXTERNAL_CORE.md` with G version progression and explicit “ECF structural coherence != task correctness/Assurance” boundary.
- [ ] **Step 4:** Run all `test_external_core_a2_*`, `test_external_core_g*`, prior Operations/Research/Assurance suites and repository Refoundation gates.
- [ ] **Step 5:** Commit `feat(external-core): integrate A2 coherence fabric across A-G`.

---

### Task 8: Hosted Verification and PR Closure

**Files:** add a dedicated A2 workflow only if existing Refoundation path filters omit the new files; update PR #337 body with exact evidence.

- [ ] **Step 1:** Inspect PR-triggered workflow runs on exact final head for Python 3.11 and 3.13 where repository acceptance requires both.
- [ ] **Step 2:** For any failure, apply systematic debugging and classify it before editing code; never weaken tests merely to obtain green.
- [ ] **Step 3:** Before any completion claim require: G1/G2/G3 green; A2 component/handoff/audit/matrix green; prior Ops/Research green; authoritative Refoundation gate green on exact head or an explicitly proven unrelated blocker; audit CLI clean on canonical declarations; no TODO/TBD/placeholders in new production/spec/plan; diff shows no authority relocation from A–F to ECF/G.
- [ ] **Step 4:** Mark PR ready only after evidence is attached. Do not auto-merge unless explicitly requested.
