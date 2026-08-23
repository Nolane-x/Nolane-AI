from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .campaign_tasks import CampaignPartition, CampaignTaskRegistry
from .types import canonical_digest


class ContaminationKind(str, Enum):
    HELDOUT_TASK_REF = 'heldout_task_ref'
    HELDOUT_OBJECTIVE_REF = 'heldout_objective_ref'
    HELDOUT_ACCEPTANCE_REF = 'heldout_acceptance_ref'
    HELDOUT_TAG_REF = 'heldout_tag_ref'


@dataclass(frozen=True, slots=True)
class ContaminationFinding:
    finding_id: str
    campaign_id: str
    task_ids: tuple[str, ...]
    training_refs: tuple[str, ...]
    distillation_refs: tuple[str, ...]
    personal_skill_refs: tuple[str, ...]
    kinds: tuple[ContaminationKind, ...]
    quarantined: bool
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'finding_id': self.finding_id, 'campaign_id': self.campaign_id,
            'task_ids': list(self.task_ids), 'training_refs': list(self.training_refs),
            'distillation_refs': list(self.distillation_refs), 'personal_skill_refs': list(self.personal_skill_refs),
            'kinds': [x.value for x in self.kinds], 'quarantined': self.quarantined,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ContaminationFinding':
        row = cls(
            finding_id=str(state['finding_id']), campaign_id=str(state['campaign_id']),
            task_ids=tuple(str(x) for x in state.get('task_ids', ())),
            training_refs=tuple(str(x) for x in state.get('training_refs', ())),
            distillation_refs=tuple(str(x) for x in state.get('distillation_refs', ())),
            personal_skill_refs=tuple(str(x) for x in state.get('personal_skill_refs', ())),
            kinds=tuple(ContaminationKind(str(x)) for x in state.get('kinds', ())),
            quarantined=bool(state['quarantined']), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('campaign contamination finding digest mismatch')
        if row.quarantined != bool(row.kinds):
            raise ValueError('campaign contamination disposition is non-canonical')
        return row


class CampaignContaminationLedger:
    def __init__(self, *, tasks: CampaignTaskRegistry, findings: tuple[ContaminationFinding, ...] = ()) -> None:
        self.tasks = tasks
        self._findings: dict[str, ContaminationFinding] = {}
        self._latest: dict[str, str] = {}
        for row in findings:
            for task_id in row.task_ids: self.tasks.get(task_id)
            if row.finding_id in self._findings:
                raise ValueError('duplicate contamination finding id')
            self._findings[row.finding_id] = row
            self._latest[row.campaign_id] = row.finding_id

    def scan(
        self,
        *,
        campaign_id: str,
        task_ids: tuple[str, ...],
        training_refs: tuple[str, ...],
        distillation_refs: tuple[str, ...],
        personal_skill_refs: tuple[str, ...],
    ) -> ContaminationFinding:
        campaign_id = str(campaign_id).strip()
        if not campaign_id:
            raise ValueError('campaign id must be explicit')
        task_ids = tuple(str(x) for x in task_ids)
        all_refs = set(str(x) for x in (*training_refs, *distillation_refs, *personal_skill_refs))
        kinds: set[ContaminationKind] = set()
        for task_id in task_ids:
            task = self.tasks.get(task_id)
            if self.tasks.partition_of(task_id) is not CampaignPartition.HELDOUT:
                continue
            if task.task_id in all_refs:
                kinds.add(ContaminationKind.HELDOUT_TASK_REF)
            if task.objective_digest in all_refs:
                kinds.add(ContaminationKind.HELDOUT_OBJECTIVE_REF)
            if task.acceptance_command_digest in all_refs:
                kinds.add(ContaminationKind.HELDOUT_ACCEPTANCE_REF)
            if any(tag in all_refs for tag in task.contamination_tags):
                kinds.add(ContaminationKind.HELDOUT_TAG_REF)
        ordered_kinds = tuple(sorted(kinds, key=lambda x: x.value))
        payload0 = {
            'campaign_id': campaign_id, 'task_ids': list(task_ids),
            'training_refs': sorted(str(x) for x in training_refs),
            'distillation_refs': sorted(str(x) for x in distillation_refs),
            'personal_skill_refs': sorted(str(x) for x in personal_skill_refs),
            'kinds': [x.value for x in ordered_kinds], 'quarantined': bool(ordered_kinds),
        }
        finding_id = 'campaign-contamination-' + canonical_digest(payload0)[:24]
        payload = {'finding_id': finding_id, **payload0}
        row = ContaminationFinding(
            finding_id=finding_id, campaign_id=campaign_id, task_ids=task_ids,
            training_refs=tuple(payload0['training_refs']), distillation_refs=tuple(payload0['distillation_refs']),
            personal_skill_refs=tuple(payload0['personal_skill_refs']), kinds=ordered_kinds,
            quarantined=bool(ordered_kinds), digest=canonical_digest(payload),
        )
        self._findings.setdefault(row.finding_id, row)
        self._latest[campaign_id] = row.finding_id
        return self._findings[row.finding_id]

    def latest_for(self, campaign_id: str) -> ContaminationFinding:
        try:
            return self._findings[self._latest[str(campaign_id)]]
        except KeyError as exc:
            raise KeyError(f'campaign has no contamination scan: {campaign_id}') from exc

    def to_state(self) -> dict[str, Any]:
        return {'findings': [self._findings[k].to_state() for k in sorted(self._findings)]}

    @classmethod
    def from_state(cls, *, tasks: CampaignTaskRegistry, state: Mapping[str, Any]) -> 'CampaignContaminationLedger':
        return cls(tasks=tasks, findings=tuple(ContaminationFinding.from_state(x) for x in state.get('findings', ())))
