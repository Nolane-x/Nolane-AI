from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from .coordination import CoordinationControlPlane
from .foundry_resources import FoundryBudget
from .registry import AgentRegistry
from .tasks import TaskGraph
from .types import AgentRank, canonical_digest


class SpawnStatus(str, Enum):
    REQUESTED = 'requested'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    INSTANTIATED = 'instantiated'


@dataclass(frozen=True, slots=True)
class FoundryTemplate:
    template_id: str
    capabilities: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    allowed_external_cores: tuple[str, ...]
    allowed_artifact_kinds: tuple[str, ...]
    digest: str = ''

    def __post_init__(self) -> None:
        if not self.template_id.strip() or not self.capabilities:
            raise ValueError('Foundry template identity and capabilities must be explicit')
        canonical = canonical_digest(self.payload())
        if self.digest and self.digest != canonical:
            raise ValueError('Foundry template digest mismatch')
        if not self.digest:
            object.__setattr__(self, 'digest', canonical)

    def payload(self) -> dict[str, Any]:
        return {
            'template_id': self.template_id,
            'capabilities': list(self.capabilities),
            'allowed_tools': list(self.allowed_tools),
            'allowed_external_cores': list(self.allowed_external_cores),
            'allowed_artifact_kinds': list(self.allowed_artifact_kinds),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'FoundryTemplate':
        return cls(
            template_id=str(state['template_id']),
            capabilities=tuple(str(x) for x in state.get('capabilities', ())),
            allowed_tools=tuple(str(x) for x in state.get('allowed_tools', ())),
            allowed_external_cores=tuple(str(x) for x in state.get('allowed_external_cores', ())),
            allowed_artifact_kinds=tuple(str(x) for x in state.get('allowed_artifact_kinds', ())),
            digest=str(state.get('digest', '')),
        )


@dataclass(frozen=True, slots=True)
class SpawnRequest:
    request_id: str
    sponsor_agent_id: str
    parent_task_id: str | None
    template_id: str
    mission: str
    team_id: str
    budget: FoundryBudget
    requested_tools: tuple[str, ...]
    requested_external_cores: tuple[str, ...]
    allowed_artifact_kinds: tuple[str, ...]
    created_token: int
    status: SpawnStatus
    approved_by: str | None
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'request_id': self.request_id,
            'sponsor_agent_id': self.sponsor_agent_id,
            'parent_task_id': self.parent_task_id,
            'template_id': self.template_id,
            'mission': self.mission,
            'team_id': self.team_id,
            'budget': self.budget.to_state(),
            'requested_tools': list(self.requested_tools),
            'requested_external_cores': list(self.requested_external_cores),
            'allowed_artifact_kinds': list(self.allowed_artifact_kinds),
            'created_token': self.created_token,
            'status': self.status.value,
            'approved_by': self.approved_by,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'SpawnRequest':
        row = cls(
            request_id=str(state['request_id']),
            sponsor_agent_id=str(state['sponsor_agent_id']),
            parent_task_id=None if state.get('parent_task_id') is None else str(state['parent_task_id']),
            template_id=str(state['template_id']),
            mission=str(state['mission']),
            team_id=str(state['team_id']),
            budget=FoundryBudget.from_state(state['budget']),
            requested_tools=tuple(str(x) for x in state.get('requested_tools', ())),
            requested_external_cores=tuple(str(x) for x in state.get('requested_external_cores', ())),
            allowed_artifact_kinds=tuple(str(x) for x in state.get('allowed_artifact_kinds', ())),
            created_token=int(state['created_token']),
            status=SpawnStatus(str(state['status'])),
            approved_by=None if state.get('approved_by') is None else str(state['approved_by']),
            digest=str(state['digest']),
        )
        if row.created_token < 0:
            raise ValueError('Foundry spawn token must be non-negative')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('Foundry spawn request digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class EphemeralIdentityManifest:
    ephemeral_id: str
    request_id: str
    team_id: str
    sponsor_agent_id: str
    parent_task_id: str | None
    template_id: str
    mission: str
    allowed_tools: tuple[str, ...]
    allowed_external_cores: tuple[str, ...]
    allowed_artifact_kinds: tuple[str, ...]
    memory_namespace: str
    generation: int
    created_token: int
    expires_token: int
    parent_lease_id: str | None
    parent_lease_epoch: int | None
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'ephemeral_id': self.ephemeral_id,
            'request_id': self.request_id,
            'team_id': self.team_id,
            'sponsor_agent_id': self.sponsor_agent_id,
            'parent_task_id': self.parent_task_id,
            'template_id': self.template_id,
            'mission': self.mission,
            'allowed_tools': list(self.allowed_tools),
            'allowed_external_cores': list(self.allowed_external_cores),
            'allowed_artifact_kinds': list(self.allowed_artifact_kinds),
            'memory_namespace': self.memory_namespace,
            'generation': self.generation,
            'created_token': self.created_token,
            'expires_token': self.expires_token,
            'parent_lease_id': self.parent_lease_id,
            'parent_lease_epoch': self.parent_lease_epoch,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'EphemeralIdentityManifest':
        row = cls(
            ephemeral_id=str(state['ephemeral_id']),
            request_id=str(state['request_id']),
            team_id=str(state['team_id']),
            sponsor_agent_id=str(state['sponsor_agent_id']),
            parent_task_id=None if state.get('parent_task_id') is None else str(state['parent_task_id']),
            template_id=str(state['template_id']),
            mission=str(state['mission']),
            allowed_tools=tuple(str(x) for x in state.get('allowed_tools', ())),
            allowed_external_cores=tuple(str(x) for x in state.get('allowed_external_cores', ())),
            allowed_artifact_kinds=tuple(str(x) for x in state.get('allowed_artifact_kinds', ())),
            memory_namespace=str(state['memory_namespace']),
            generation=int(state['generation']),
            created_token=int(state['created_token']),
            expires_token=int(state['expires_token']),
            parent_lease_id=None if state.get('parent_lease_id') is None else str(state['parent_lease_id']),
            parent_lease_epoch=None if state.get('parent_lease_epoch') is None else int(state['parent_lease_epoch']),
            digest=str(state['digest']),
        )
        if row.generation <= 0 or row.created_token < 0 or row.expires_token <= row.created_token:
            raise ValueError('invalid Foundry manifest generation/lifetime')
        if (row.parent_lease_id is None) != (row.parent_lease_epoch is None):
            raise ValueError('Foundry parent lease id and epoch must appear together')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('Foundry manifest digest mismatch')
        return row


def _templates() -> tuple[FoundryTemplate, ...]:
    return (
        FoundryTemplate(
            'hypothesis-explorer',
            ('hypothesis_generation', 'counterfactual_reasoning', 'evidence_synthesis'),
            ('memory', 'task-graph', 'evidence-store'),
            ('knowledge-graph',),
            ('hypothesis', 'evidence'),
        ),
        FoundryTemplate(
            'repository-archaeologist',
            ('history_trace', 'convention_recovery', 'change_causality'),
            ('filesystem', 'git', 'code-search', 'evidence-store'),
            ('github-research', 'repo-graph'),
            ('research-note', 'evidence'),
        ),
        FoundryTemplate(
            'fuzz-counterexample',
            ('fuzzing', 'counterexample_minimization', 'property_attack'),
            ('filesystem', 'terminal', 'test-runner', 'evidence-store'),
            ('fuzzer', 'fresh-sandbox'),
            ('counterexample', 'test-evidence', 'evidence'),
        ),
        FoundryTemplate(
            'bug-reproducer',
            ('failure_reproduction', 'trace_analysis', 'minimization'),
            ('filesystem', 'terminal', 'test-runner', 'git', 'evidence-store'),
            ('runtime-tracer', 'failure-minimizer'),
            ('reproduction', 'trace', 'evidence'),
        ),
        FoundryTemplate(
            'migration-compatibility',
            ('schema_reasoning', 'migration_planning', 'compatibility_analysis'),
            ('filesystem', 'git', 'terminal', 'test-runner', 'evidence-store'),
            ('schema-graph', 'migration-planner', 'compatibility-matrix'),
            ('migration-proposal', 'compatibility-evidence', 'evidence'),
        ),
    )


def _signed_request(**kwargs: Any) -> SpawnRequest:
    temp = SpawnRequest(digest='', **kwargs)
    return replace(temp, digest=canonical_digest(temp.payload()))


def _signed_manifest(**kwargs: Any) -> EphemeralIdentityManifest:
    temp = EphemeralIdentityManifest(digest='', **kwargs)
    return replace(temp, digest=canonical_digest(temp.payload()))


class FoundryProfileRegistry:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        tasks: TaskGraph,
        coordination: CoordinationControlPlane,
        templates: tuple[FoundryTemplate, ...] | None = None,
        requests: tuple[SpawnRequest, ...] = (),
        manifests: tuple[EphemeralIdentityManifest, ...] = (),
        generation_counter: int = 0,
    ) -> None:
        self.registry = registry
        self.tasks = tasks
        self.coordination = coordination
        template_rows = templates or _templates()
        self._templates = {row.template_id: row for row in template_rows}
        if len(self._templates) != len(template_rows):
            raise ValueError('duplicate Foundry template id')
        self._requests: dict[str, SpawnRequest] = {}
        for row in requests:
            self._validate_request(row)
            if row.request_id in self._requests:
                raise ValueError('duplicate Foundry request id')
            self._requests[row.request_id] = row
        self._manifests: dict[str, EphemeralIdentityManifest] = {}
        for row in manifests:
            self._validate_manifest(row)
            if row.ephemeral_id in self._manifests:
                raise ValueError('duplicate Foundry ephemeral id')
            self._manifests[row.ephemeral_id] = row
        self._generation_counter = int(generation_counter)
        if self._generation_counter < len(self._manifests):
            raise ValueError('Foundry generation counter is not canonical')

    def templates(self) -> tuple[FoundryTemplate, ...]:
        return tuple(self._templates[key] for key in sorted(self._templates))

    def get_template(self, template_id: str) -> FoundryTemplate:
        try:
            return self._templates[str(template_id)]
        except KeyError as exc:
            raise KeyError(f'unknown Foundry template: {template_id}') from exc

    def _validate_sponsor_scope(self, sponsor_agent_id: str, parent_task_id: str | None) -> None:
        sponsor = self.registry.get(sponsor_agent_id)
        if sponsor.rank not in (AgentRank.CENTRAL, AgentRank.CHIEF):
            raise PermissionError('only Nolane Central or a Regional Chief may sponsor Foundry workers')
        if sponsor.rank is AgentRank.CENTRAL:
            if parent_task_id is not None:
                self.tasks.get(parent_task_id)
            return
        if parent_task_id is None:
            raise PermissionError('Regional Chief Foundry spawn requires a parent task')
        task = self.tasks.get(parent_task_id)
        if task.leased_to is None:
            raise PermissionError('Regional Chief Foundry spawn requires an actively leased parent task')
        holder = self.registry.get(task.leased_to)
        if holder.region != sponsor.region:
            raise PermissionError('Regional Chief cannot spawn Foundry workers outside its region task boundary')

    @staticmethod
    def _subset(values: tuple[str, ...], allowed: tuple[str, ...], label: str) -> tuple[str, ...]:
        normalized = tuple(sorted({str(x) for x in values if str(x).strip()}))
        if any(value not in allowed for value in normalized):
            raise PermissionError(f'Foundry requested {label} exceeds template capability envelope')
        return normalized

    def request(
        self,
        *,
        sponsor_agent_id: str,
        parent_task_id: str | None,
        template_id: str,
        mission: str,
        team_id: str,
        budget: FoundryBudget,
        requested_tools: tuple[str, ...] = (),
        requested_external_cores: tuple[str, ...] = (),
        allowed_artifact_kinds: tuple[str, ...] = (),
        current_token: int = 0,
    ) -> SpawnRequest:
        if current_token < 0:
            raise ValueError('Foundry current token must be non-negative')
        mission = str(mission).strip()
        team_id = str(team_id).strip()
        if not mission or not team_id:
            raise ValueError('Foundry mission and team id must be explicit')
        self._validate_sponsor_scope(str(sponsor_agent_id), None if parent_task_id is None else str(parent_task_id))
        template = self.get_template(template_id)
        tools = self._subset(
            requested_tools or template.allowed_tools,
            template.allowed_tools,
            'tools',
        )
        cores = self._subset(
            requested_external_cores or template.allowed_external_cores,
            template.allowed_external_cores,
            'external cores',
        )
        artifact_kinds = self._subset(
            allowed_artifact_kinds or template.allowed_artifact_kinds,
            template.allowed_artifact_kinds,
            'artifact kinds',
        )
        core_payload = {
            'sponsor_agent_id': str(sponsor_agent_id),
            'parent_task_id': None if parent_task_id is None else str(parent_task_id),
            'template_id': template.template_id,
            'mission': mission,
            'team_id': team_id,
            'budget': budget.to_state(),
            'requested_tools': list(tools),
            'requested_external_cores': list(cores),
            'allowed_artifact_kinds': list(artifact_kinds),
            'created_token': int(current_token),
        }
        request_id = 'foundry-request-' + canonical_digest(core_payload)[:24]
        row = _signed_request(
            request_id=request_id,
            sponsor_agent_id=str(sponsor_agent_id),
            parent_task_id=None if parent_task_id is None else str(parent_task_id),
            template_id=template.template_id,
            mission=mission,
            team_id=team_id,
            budget=budget,
            requested_tools=tools,
            requested_external_cores=cores,
            allowed_artifact_kinds=artifact_kinds,
            created_token=int(current_token),
            status=SpawnStatus.REQUESTED,
            approved_by=None,
        )
        existing = self._requests.get(row.request_id)
        if existing is not None:
            return existing
        self._requests[row.request_id] = row
        return row

    def approve(self, request_id: str, actor_agent_id: str) -> SpawnRequest:
        old = self.get_request(request_id)
        actor = self.registry.get(actor_agent_id)
        if old.status is SpawnStatus.APPROVED and old.approved_by == actor.agent_id:
            return old
        if old.status is not SpawnStatus.REQUESTED:
            raise ValueError('only requested Foundry spawn may be approved')
        sponsor = self.registry.get(old.sponsor_agent_id)
        if actor.rank is not AgentRank.CENTRAL and actor.agent_id != sponsor.agent_id:
            raise PermissionError('Foundry spawn approval requires Central or the sponsoring Regional Chief')
        if actor.rank not in (AgentRank.CENTRAL, AgentRank.CHIEF):
            raise PermissionError('Foundry spawn approval requires Central or Regional Chief authority')
        self._validate_sponsor_scope(old.sponsor_agent_id, old.parent_task_id)
        row = _signed_request(
            request_id=old.request_id,
            sponsor_agent_id=old.sponsor_agent_id,
            parent_task_id=old.parent_task_id,
            template_id=old.template_id,
            mission=old.mission,
            team_id=old.team_id,
            budget=old.budget,
            requested_tools=old.requested_tools,
            requested_external_cores=old.requested_external_cores,
            allowed_artifact_kinds=old.allowed_artifact_kinds,
            created_token=old.created_token,
            status=SpawnStatus.APPROVED,
            approved_by=actor.agent_id,
        )
        self._requests[row.request_id] = row
        return row

    def instantiate(self, request_id: str, *, current_token: int) -> EphemeralIdentityManifest:
        request = self.get_request(request_id)
        if request.status is not SpawnStatus.APPROVED:
            raise PermissionError('Foundry spawn must be approved before instantiation')
        if current_token < request.created_token:
            raise ValueError('Foundry instantiation token cannot predate request')
        parent_lease_id: str | None = None
        parent_lease_epoch: int | None = None
        if request.parent_task_id is not None:
            try:
                lease = self.coordination.current_lease(request.parent_task_id)
            except KeyError as exc:
                raise PermissionError('Foundry parent task has no active coordination lease') from exc
            parent_lease_id = lease.lease_id
            parent_lease_epoch = lease.epoch
        self._generation_counter += 1
        identity_payload = {
            'request_id': request.request_id,
            'generation': self._generation_counter,
            'created_token': int(current_token),
            'parent_lease_id': parent_lease_id,
            'parent_lease_epoch': parent_lease_epoch,
        }
        ephemeral_id = 'ephemeral-' + canonical_digest(identity_payload)[:24]
        try:
            self.registry.get(ephemeral_id)
        except KeyError:
            pass
        else:
            raise ValueError('Foundry ephemeral id collides with permanent AgentRegistry identity')
        manifest = _signed_manifest(
            ephemeral_id=ephemeral_id,
            request_id=request.request_id,
            team_id=request.team_id,
            sponsor_agent_id=request.sponsor_agent_id,
            parent_task_id=request.parent_task_id,
            template_id=request.template_id,
            mission=request.mission,
            allowed_tools=request.requested_tools,
            allowed_external_cores=request.requested_external_cores,
            allowed_artifact_kinds=request.allowed_artifact_kinds,
            memory_namespace=f'ephemeral/{ephemeral_id}',
            generation=self._generation_counter,
            created_token=int(current_token),
            expires_token=int(current_token) + request.budget.lifetime_tokens,
            parent_lease_id=parent_lease_id,
            parent_lease_epoch=parent_lease_epoch,
        )
        self._manifests[manifest.ephemeral_id] = manifest
        self._requests[request.request_id] = _signed_request(
            request_id=request.request_id,
            sponsor_agent_id=request.sponsor_agent_id,
            parent_task_id=request.parent_task_id,
            template_id=request.template_id,
            mission=request.mission,
            team_id=request.team_id,
            budget=request.budget,
            requested_tools=request.requested_tools,
            requested_external_cores=request.requested_external_cores,
            allowed_artifact_kinds=request.allowed_artifact_kinds,
            created_token=request.created_token,
            status=SpawnStatus.INSTANTIATED,
            approved_by=request.approved_by,
        )
        return manifest

    def get_request(self, request_id: str) -> SpawnRequest:
        try:
            return self._requests[str(request_id)]
        except KeyError as exc:
            raise KeyError(f'unknown Foundry spawn request: {request_id}') from exc

    def get_manifest(self, ephemeral_id: str) -> EphemeralIdentityManifest:
        try:
            return self._manifests[str(ephemeral_id)]
        except KeyError as exc:
            raise KeyError(f'unknown Foundry ephemeral identity: {ephemeral_id}') from exc

    def requests(self) -> tuple[SpawnRequest, ...]:
        return tuple(self._requests[key] for key in sorted(self._requests))

    def manifests(self) -> tuple[EphemeralIdentityManifest, ...]:
        return tuple(self._manifests[key] for key in sorted(self._manifests))

    def _validate_request(self, row: SpawnRequest) -> None:
        self.registry.get(row.sponsor_agent_id)
        self.get_template(row.template_id)
        if row.parent_task_id is not None:
            self.tasks.get(row.parent_task_id)
        if row.approved_by is not None:
            self.registry.get(row.approved_by)
        self._subset(row.requested_tools, self.get_template(row.template_id).allowed_tools, 'tools')
        self._subset(row.requested_external_cores, self.get_template(row.template_id).allowed_external_cores, 'external cores')
        self._subset(row.allowed_artifact_kinds, self.get_template(row.template_id).allowed_artifact_kinds, 'artifact kinds')

    def _validate_manifest(self, row: EphemeralIdentityManifest) -> None:
        request = self._requests.get(row.request_id)
        if request is None:
            raise ValueError('Foundry manifest references unknown spawn request')
        if request.sponsor_agent_id != row.sponsor_agent_id or request.team_id != row.team_id:
            raise ValueError('Foundry manifest disagrees with spawn request')
        self.registry.get(row.sponsor_agent_id)
        try:
            self.registry.get(row.ephemeral_id)
        except KeyError:
            pass
        else:
            raise ValueError('Foundry snapshot attempts to install ephemeral identity into permanent registry')
        if row.parent_task_id is not None:
            self.tasks.get(row.parent_task_id)

    def to_state(self) -> dict[str, Any]:
        return {
            'templates': [row.to_state() for row in self.templates()],
            'requests': [row.to_state() for row in self.requests()],
            'manifests': [row.to_state() for row in self.manifests()],
            'generation_counter': self._generation_counter,
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        tasks: TaskGraph,
        coordination: CoordinationControlPlane,
        state: Mapping[str, Any],
    ) -> 'FoundryProfileRegistry':
        if not state:
            return cls(registry=registry, tasks=tasks, coordination=coordination)
        templates = tuple(FoundryTemplate.from_state(x) for x in state.get('templates', ()))
        requests = tuple(SpawnRequest.from_state(x) for x in state.get('requests', ()))
        manifests = tuple(EphemeralIdentityManifest.from_state(x) for x in state.get('manifests', ()))
        return cls(
            registry=registry,
            tasks=tasks,
            coordination=coordination,
            templates=templates or None,
            requests=requests,
            manifests=manifests,
            generation_counter=int(state.get('generation_counter', len(manifests))),
        )
