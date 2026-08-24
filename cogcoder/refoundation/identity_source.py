from __future__ import annotations

from cogcoder.organization.artifacts import ArtifactStore
from cogcoder.organization.authority import AuthorityGraph
from cogcoder.organization.evolution import SkillEvolutionEngine
from cogcoder.organization.events import EventLedger
from cogcoder.organization.external_core import build_default_external_core_registry
from cogcoder.organization.memory import MemoryFabric
from cogcoder.organization.registry import AgentRegistry
from cogcoder.organization.scheduler import WakeSleepScheduler
from cogcoder.organization.self_model import SelfModelRegistry
from cogcoder.organization.tasks import TaskGraph
from nolane.schemas.identity import AgentIdentity, AgentRank
from cogcoder.organization.types import EventKind
from cogcoder.organization.verification import VerificationAuthority

from .accepted_runtime import AcceptedOrganizationRuntime
from .manifests import AgentManifest, build_bootstrap_agent_manifests


_AUTHORITY_OWNERS: tuple[tuple[str, str], ...] = (
    ("master-plan", "planning.chief"),
    ("requirements", "requirements.chief"),
    ("architecture-graph", "architecture.chief"),
    ("integration-state", "integration.chief"),
    ("verification-state", "verification.chief"),
    ("frontend-ui-state", "frontend.chief"),
    ("ux-design-state", "ux.chief"),
    ("data-state", "data.chief"),
    ("infrastructure-state", "infrastructure.chief"),
    ("reliability-state", "reliability.chief"),
    ("research-state", "research.chief"),
    ("memory-intelligence-state", "memory.chief"),
)

_CENTRAL_BROADCAST_KINDS: tuple[EventKind, ...] = (
    EventKind.CENTRAL_INTERVENTION,
    EventKind.CENTRAL_QUESTION,
    EventKind.CENTRAL_CORRECTION,
    EventKind.CENTRAL_REDIRECT,
    EventKind.CENTRAL_PAUSE,
    EventKind.CENTRAL_ABORT,
    EventKind.CENTRAL_REQUEST_EVIDENCE,
)


def identity_from_manifest(manifest: AgentManifest) -> AgentIdentity:
    """Rehydrate the accepted identity contract from canonical manifest state."""
    return AgentIdentity.from_state(manifest.identity_state())


def build_canonical_agent_identities(
    manifests: tuple[AgentManifest, ...] | None = None,
) -> tuple[AgentIdentity, ...]:
    rows = tuple(identity_from_manifest(row) for row in (manifests or build_bootstrap_agent_manifests()))
    if len(rows) != 67 or len({row.agent_id for row in rows}) != 67:
        raise ValueError("canonical identity authority requires exactly 67 unique permanent identities")
    central = tuple(row for row in rows if row.rank is AgentRank.CENTRAL)
    chiefs = tuple(row for row in rows if row.rank is AgentRank.CHIEF)
    if len(central) != 1 or central[0].agent_id != "nolane.central" or len(chiefs) != 15:
        raise ValueError("canonical identity authority violates Central/Regional Chief cardinality")
    return rows


def build_manifest_driven_runtime(
    manifests: tuple[AgentManifest, ...] | None = None,
) -> AcceptedOrganizationRuntime:
    """Build the accepted implementation through the Epoch-0 compatibility membrane.

    Permanent-identity authority comes from canonical manifests. Runtime
    behavior remains the accepted implementation during zero-loss migration,
    but callers in the refoundation layer no longer import the historical
    runtime inheritance chain directly.
    """

    registry = AgentRegistry(build_canonical_agent_identities(manifests))
    ledger = EventLedger()
    authority = AuthorityGraph(registry)
    for object_id, owner_id in _AUTHORITY_OWNERS:
        authority.claim_owner(object_id, owner_id)

    for identity in registry.identities():
        if identity.rank is AgentRank.CHIEF:
            for kind in _CENTRAL_BROADCAST_KINDS:
                ledger.subscribe(identity.agent_id, kind, region=identity.region)
    ledger.subscribe("planning.chief", EventKind.PLAN_GAP_DETECTED)

    memory = MemoryFabric()
    tasks = TaskGraph(ledger=ledger, registry=registry, authority=authority)
    scheduler = WakeSleepScheduler(registry=registry, ledger=ledger)
    evolution = SkillEvolutionEngine()
    verification = VerificationAuthority(registry=registry, ledger=ledger)
    artifacts = ArtifactStore()
    external_cores = build_default_external_core_registry(registry)
    self_models = SelfModelRegistry(registry)

    return AcceptedOrganizationRuntime(
        registry=registry,
        ledger=ledger,
        authority=authority,
        memory=memory,
        tasks=tasks,
        scheduler=scheduler,
        evolution=evolution,
        verification=verification,
        artifacts=artifacts,
        external_cores=external_cores,
        self_models=self_models,
    )
