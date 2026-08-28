from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.evaluation.campaign import CampaignStatus, EvaluationCampaignControlPlane
from nolane.evaluation.campaign_tasks import CampaignTaskRegistry
from nolane.evaluation.regimes import EvaluationMode
from nolane.core.canonical_digest import canonical_digest


@dataclass(frozen=True, slots=True)
class CampaignRunSpec:
    run_id: str
    campaign_id: str
    task_id: str
    mode: EvaluationMode
    producer_revision: str
    environment_digest: str
    toolchain_digest: str
    campaign_freeze_digest: str
    task_digest: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'run_id': self.run_id, 'campaign_id': self.campaign_id, 'task_id': self.task_id,
            'mode': self.mode.value, 'producer_revision': self.producer_revision,
            'environment_digest': self.environment_digest, 'toolchain_digest': self.toolchain_digest,
            'campaign_freeze_digest': self.campaign_freeze_digest, 'task_digest': self.task_digest,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CampaignRunSpec':
        row = cls(
            run_id=str(state['run_id']), campaign_id=str(state['campaign_id']), task_id=str(state['task_id']),
            mode=EvaluationMode(str(state['mode'])), producer_revision=str(state['producer_revision']),
            environment_digest=str(state['environment_digest']), toolchain_digest=str(state['toolchain_digest']),
            campaign_freeze_digest=str(state['campaign_freeze_digest']), task_digest=str(state['task_digest']),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('campaign run spec digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class CampaignRunReceipt:
    run_id: str
    spec_digest: str
    passed: bool
    false_accepts: int
    regressions: int
    compute_units: int
    tool_calls: int
    external_core_calls: int
    wall_clock_ms: int
    energy_joules: float | None
    active_agents: int
    output_artifact_ids: tuple[str, ...]
    termination_reason: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'run_id': self.run_id, 'spec_digest': self.spec_digest, 'passed': self.passed,
            'false_accepts': self.false_accepts, 'regressions': self.regressions,
            'compute_units': self.compute_units, 'tool_calls': self.tool_calls,
            'external_core_calls': self.external_core_calls, 'wall_clock_ms': self.wall_clock_ms,
            'energy_joules': self.energy_joules, 'active_agents': self.active_agents,
            'output_artifact_ids': list(self.output_artifact_ids), 'termination_reason': self.termination_reason,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CampaignRunReceipt':
        row = cls(
            run_id=str(state['run_id']), spec_digest=str(state['spec_digest']), passed=bool(state['passed']),
            false_accepts=int(state['false_accepts']), regressions=int(state['regressions']),
            compute_units=int(state['compute_units']), tool_calls=int(state['tool_calls']),
            external_core_calls=int(state['external_core_calls']), wall_clock_ms=int(state['wall_clock_ms']),
            energy_joules=None if state.get('energy_joules') is None else float(state['energy_joules']),
            active_agents=int(state['active_agents']),
            output_artifact_ids=tuple(str(x) for x in state.get('output_artifact_ids', ())),
            termination_reason=str(state['termination_reason']), digest=str(state['digest']),
        )
        _validate_receipt(row)
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('campaign run receipt digest mismatch')
        return row


def _validate_receipt(row: CampaignRunReceipt) -> None:
    if not row.run_id.strip() or not row.spec_digest.strip() or not row.termination_reason.strip():
        raise ValueError('campaign run receipt identity and termination reason must be explicit')
    for value in (row.false_accepts, row.regressions, row.compute_units, row.tool_calls, row.external_core_calls, row.wall_clock_ms):
        if value < 0:
            raise ValueError('campaign run counters must be non-negative')
    if row.active_agents <= 0:
        raise ValueError('campaign run requires positive active agent count')
    if row.energy_joules is not None and row.energy_joules < 0:
        raise ValueError('campaign energy estimate must be non-negative')
    if not row.output_artifact_ids:
        raise ValueError('campaign run requires output evidence artifacts')


class CampaignRunLedger:
    def __init__(
        self,
        *,
        campaigns: EvaluationCampaignControlPlane,
        tasks: CampaignTaskRegistry,
        specs: tuple[CampaignRunSpec, ...] = (),
        receipts: tuple[CampaignRunReceipt, ...] = (),
    ) -> None:
        self.campaigns = campaigns
        self.tasks = tasks
        self._specs: dict[str, CampaignRunSpec] = {}
        self._receipts: dict[str, CampaignRunReceipt] = {}
        for row in specs:
            self._validate_spec(row)
            if row.run_id in self._specs:
                raise ValueError('duplicate campaign run id')
            self._specs[row.run_id] = row
        for row in receipts:
            spec = self.get_spec(row.run_id)
            if row.spec_digest != spec.digest:
                raise ValueError('campaign run receipt does not bind run spec')
            if row.run_id in self._receipts:
                raise ValueError('duplicate campaign run receipt')
            self._receipts[row.run_id] = row

    def _validate_spec(self, row: CampaignRunSpec) -> None:
        campaign = self.campaigns.get(row.campaign_id)
        task = self.tasks.get(row.task_id)
        if row.task_id not in campaign.task_ids:
            raise ValueError('run spec task is outside campaign')
        if row.mode not in campaign.modes:
            raise PermissionError('run spec mode was not declared by frozen campaign')
        if not campaign.freeze_digest or row.campaign_freeze_digest != campaign.freeze_digest:
            raise ValueError('run spec campaign freeze digest mismatch')
        if row.task_digest != task.digest:
            raise ValueError('run spec task digest mismatch')
        if not all(str(x).strip() for x in (row.run_id, row.producer_revision, row.environment_digest, row.toolchain_digest)):
            raise ValueError('run spec identity/revision/environment/toolchain must be explicit')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('campaign run spec digest mismatch')

    def create_spec(self, **kwargs: Any) -> CampaignRunSpec:
        campaign = self.campaigns.get(str(kwargs['campaign_id']))
        if campaign.status is not CampaignStatus.RUNNING:
            raise PermissionError('campaign must be RUNNING before creating run specs')
        task = self.tasks.get(str(kwargs['task_id']))
        mode = EvaluationMode(kwargs['mode'])
        if mode not in campaign.modes:
            raise PermissionError('run mode was not declared by frozen campaign')
        row0 = CampaignRunSpec(
            run_id=str(kwargs['run_id']), campaign_id=campaign.campaign_id, task_id=task.task_id,
            mode=mode, producer_revision=str(kwargs['producer_revision']),
            environment_digest=str(kwargs['environment_digest']), toolchain_digest=str(kwargs['toolchain_digest']),
            campaign_freeze_digest=str(campaign.freeze_digest), task_digest=task.digest, digest='',
        )
        row = CampaignRunSpec(
            run_id=row0.run_id, campaign_id=row0.campaign_id, task_id=row0.task_id, mode=row0.mode,
            producer_revision=row0.producer_revision, environment_digest=row0.environment_digest,
            toolchain_digest=row0.toolchain_digest, campaign_freeze_digest=row0.campaign_freeze_digest,
            task_digest=row0.task_digest, digest=canonical_digest(row0.payload()),
        )
        self._validate_spec(row)
        existing = self._specs.get(row.run_id)
        if existing is not None:
            if existing == row:
                return existing
            raise ValueError('campaign run id cannot be rebound')
        self._specs[row.run_id] = row
        return row

    def get_spec(self, run_id: str) -> CampaignRunSpec:
        try:
            return self._specs[str(run_id)]
        except KeyError as exc:
            raise KeyError(f'unknown campaign run spec: {run_id}') from exc

    def record_result(
        self,
        *,
        run_id: str,
        passed: bool,
        false_accepts: int,
        regressions: int,
        compute_units: int,
        tool_calls: int,
        external_core_calls: int,
        wall_clock_ms: int,
        energy_joules: float | None,
        active_agents: int,
        output_artifact_ids: tuple[str, ...],
        termination_reason: str,
    ) -> CampaignRunReceipt:
        spec = self.get_spec(run_id)
        row0 = CampaignRunReceipt(
            run_id=spec.run_id, spec_digest=spec.digest, passed=bool(passed),
            false_accepts=int(false_accepts), regressions=int(regressions), compute_units=int(compute_units),
            tool_calls=int(tool_calls), external_core_calls=int(external_core_calls), wall_clock_ms=int(wall_clock_ms),
            energy_joules=None if energy_joules is None else float(energy_joules), active_agents=int(active_agents),
            output_artifact_ids=tuple(str(x) for x in output_artifact_ids),
            termination_reason=str(termination_reason), digest='',
        )
        _validate_receipt(row0)
        row = CampaignRunReceipt(
            run_id=row0.run_id, spec_digest=row0.spec_digest, passed=row0.passed,
            false_accepts=row0.false_accepts, regressions=row0.regressions, compute_units=row0.compute_units,
            tool_calls=row0.tool_calls, external_core_calls=row0.external_core_calls, wall_clock_ms=row0.wall_clock_ms,
            energy_joules=row0.energy_joules, active_agents=row0.active_agents,
            output_artifact_ids=row0.output_artifact_ids, termination_reason=row0.termination_reason,
            digest=canonical_digest(row0.payload()),
        )
        existing = self._receipts.get(row.run_id)
        if existing is not None:
            if existing == row:
                return existing
            raise ValueError('campaign run result cannot be rebound')
        self._receipts[row.run_id] = row
        return row

    def get_receipt(self, run_id: str) -> CampaignRunReceipt:
        try:
            return self._receipts[str(run_id)]
        except KeyError as exc:
            raise KeyError(f'unknown campaign run receipt: {run_id}') from exc

    def receipts_for(self, campaign_id: str, mode: EvaluationMode) -> tuple[tuple[CampaignRunSpec, CampaignRunReceipt], ...]:
        mode = EvaluationMode(mode)
        rows = []
        for run_id in sorted(self._specs):
            spec = self._specs[run_id]
            if spec.campaign_id == str(campaign_id) and spec.mode is mode and run_id in self._receipts:
                rows.append((spec, self._receipts[run_id]))
        return tuple(rows)

    def to_state(self) -> dict[str, Any]:
        return {
            'specs': [self._specs[k].to_state() for k in sorted(self._specs)],
            'receipts': [self._receipts[k].to_state() for k in sorted(self._receipts)],
        }

    @classmethod
    def from_state(
        cls, *, campaigns: EvaluationCampaignControlPlane, tasks: CampaignTaskRegistry, state: Mapping[str, Any],
    ) -> 'CampaignRunLedger':
        return cls(
            campaigns=campaigns, tasks=tasks,
            specs=tuple(CampaignRunSpec.from_state(x) for x in state.get('specs', ())),
            receipts=tuple(CampaignRunReceipt.from_state(x) for x in state.get('receipts', ())),
        )
