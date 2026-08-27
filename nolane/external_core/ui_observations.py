from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .artifacts import ArtifactStore
from .types import canonical_digest


@dataclass(frozen=True, slots=True)
class Viewport:
    width: int
    height: int
    device_scale: float = 1.0

    def __post_init__(self) -> None:
        if self.width < 1 or self.height < 1 or float(self.device_scale) <= 0:
            raise ValueError('viewport dimensions and scale must be positive')

    @property
    def viewport_class(self) -> str:
        if self.width < 768:
            return 'mobile'
        if self.width < 1200:
            return 'tablet'
        return 'desktop'

    def to_state(self) -> dict[str, Any]:
        return {'width': self.width, 'height': self.height, 'device_scale': self.device_scale}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'Viewport':
        return cls(int(state['width']), int(state['height']), float(state.get('device_scale', 1.0)))


@dataclass(frozen=True, slots=True)
class RenderObservation:
    observation_id: str
    sequence: int
    task_id: str
    work_id: str
    patch_id: str | None
    producer_agent_id: str
    viewport: Viewport
    browser_runtime_artifact_id: str
    dom_artifact_id: str
    screenshot_artifact_id: str
    cssom_artifact_id: str | None
    accessibility_tree_artifact_id: str | None
    interaction_trace_artifact_id: str | None
    evidence_refs: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'observation_id': self.observation_id,
            'sequence': self.sequence,
            'task_id': self.task_id,
            'work_id': self.work_id,
            'patch_id': self.patch_id,
            'producer_agent_id': self.producer_agent_id,
            'viewport': self.viewport.to_state(),
            'browser_runtime_artifact_id': self.browser_runtime_artifact_id,
            'dom_artifact_id': self.dom_artifact_id,
            'screenshot_artifact_id': self.screenshot_artifact_id,
            'cssom_artifact_id': self.cssom_artifact_id,
            'accessibility_tree_artifact_id': self.accessibility_tree_artifact_id,
            'interaction_trace_artifact_id': self.interaction_trace_artifact_id,
            'evidence_refs': list(self.evidence_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'RenderObservation':
        row = cls(
            observation_id=str(state['observation_id']),
            sequence=int(state['sequence']),
            task_id=str(state['task_id']),
            work_id=str(state['work_id']),
            patch_id=None if state.get('patch_id') is None else str(state['patch_id']),
            producer_agent_id=str(state['producer_agent_id']),
            viewport=Viewport.from_state(state['viewport']),
            browser_runtime_artifact_id=str(state['browser_runtime_artifact_id']),
            dom_artifact_id=str(state['dom_artifact_id']),
            screenshot_artifact_id=str(state['screenshot_artifact_id']),
            cssom_artifact_id=None if state.get('cssom_artifact_id') is None else str(state['cssom_artifact_id']),
            accessibility_tree_artifact_id=None if state.get('accessibility_tree_artifact_id') is None else str(state['accessibility_tree_artifact_id']),
            interaction_trace_artifact_id=None if state.get('interaction_trace_artifact_id') is None else str(state['interaction_trace_artifact_id']),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('UI observation digest mismatch')
        return row


class UIObservationLedger:
    _KINDS = {
        'browser_runtime_artifact_id': 'browser-runtime',
        'dom_artifact_id': 'dom-snapshot',
        'screenshot_artifact_id': 'screenshot',
        'cssom_artifact_id': 'cssom-snapshot',
        'accessibility_tree_artifact_id': 'accessibility-tree',
        'interaction_trace_artifact_id': 'interaction-trace',
    }

    def __init__(self, artifacts: ArtifactStore) -> None:
        self.artifacts = artifacts
        self._rows: dict[str, RenderObservation] = {}
        self._counter = 0

    def observations(self) -> tuple[RenderObservation, ...]:
        return tuple(self._rows[key] for key in sorted(self._rows))

    def get(self, observation_id: str) -> RenderObservation:
        try:
            return self._rows[str(observation_id)]
        except KeyError as exc:
            raise KeyError(f'unknown UI observation: {observation_id}') from exc

    def _require_kind(self, artifact_id: str | None, expected: str, *, required: bool) -> None:
        if artifact_id is None:
            if required:
                raise ValueError(f'missing required {expected} artifact')
            return
        row = self.artifacts.get(artifact_id)
        if row.kind != expected:
            raise ValueError(f'artifact {artifact_id} has kind {row.kind}, expected {expected}')

    def record(
        self,
        *,
        task_id: str,
        work_id: str,
        producer_agent_id: str,
        viewport: Viewport,
        browser_runtime_artifact_id: str,
        dom_artifact_id: str,
        screenshot_artifact_id: str,
        evidence_refs: tuple[str, ...],
        patch_id: str | None = None,
        cssom_artifact_id: str | None = None,
        accessibility_tree_artifact_id: str | None = None,
        interaction_trace_artifact_id: str | None = None,
    ) -> RenderObservation:
        if not all(str(x).strip() for x in (task_id, work_id, producer_agent_id)) or not evidence_refs:
            raise ValueError('UI observation requires task/work/producer and evidence')
        values = {
            'browser_runtime_artifact_id': browser_runtime_artifact_id,
            'dom_artifact_id': dom_artifact_id,
            'screenshot_artifact_id': screenshot_artifact_id,
            'cssom_artifact_id': cssom_artifact_id,
            'accessibility_tree_artifact_id': accessibility_tree_artifact_id,
            'interaction_trace_artifact_id': interaction_trace_artifact_id,
        }
        for field, expected in self._KINDS.items():
            self._require_kind(values[field], expected, required=field in {
                'browser_runtime_artifact_id', 'dom_artifact_id', 'screenshot_artifact_id',
            })
        self._counter += 1
        observation_id = f'ui-observation-{self._counter:08d}'
        payload = {
            'observation_id': observation_id,
            'sequence': self._counter,
            'task_id': str(task_id),
            'work_id': str(work_id),
            'patch_id': None if patch_id is None else str(patch_id),
            'producer_agent_id': str(producer_agent_id),
            'viewport': viewport.to_state(),
            **values,
            'evidence_refs': [str(x) for x in evidence_refs],
        }
        row = RenderObservation(
            observation_id=observation_id,
            sequence=self._counter,
            task_id=str(task_id),
            work_id=str(work_id),
            patch_id=None if patch_id is None else str(patch_id),
            producer_agent_id=str(producer_agent_id),
            viewport=viewport,
            browser_runtime_artifact_id=str(browser_runtime_artifact_id),
            dom_artifact_id=str(dom_artifact_id),
            screenshot_artifact_id=str(screenshot_artifact_id),
            cssom_artifact_id=None if cssom_artifact_id is None else str(cssom_artifact_id),
            accessibility_tree_artifact_id=None if accessibility_tree_artifact_id is None else str(accessibility_tree_artifact_id),
            interaction_trace_artifact_id=None if interaction_trace_artifact_id is None else str(interaction_trace_artifact_id),
            evidence_refs=tuple(str(x) for x in evidence_refs),
            digest=canonical_digest(payload),
        )
        self._rows[row.observation_id] = row
        return row

    def to_state(self) -> dict[str, Any]:
        return {'observations': [x.to_state() for x in self.observations()], 'counter': self._counter}

    @classmethod
    def from_state(cls, *, artifacts: ArtifactStore, state: Mapping[str, Any]) -> 'UIObservationLedger':
        ledger = cls(artifacts)
        max_counter = 0
        for value in state.get('observations', ()):
            row = RenderObservation.from_state(value)
            if row.observation_id in ledger._rows:
                raise ValueError('duplicate UI observation id')
            for field, expected in cls._KINDS.items():
                artifact_id = getattr(row, field)
                ledger._require_kind(artifact_id, expected, required=field in {
                    'browser_runtime_artifact_id', 'dom_artifact_id', 'screenshot_artifact_id',
                })
            ledger._rows[row.observation_id] = row
            max_counter = max(max_counter, row.sequence)
        ledger._counter = int(state.get('counter', max_counter))
        if ledger._counter < max_counter:
            raise ValueError('UI observation counter is behind history')
        return ledger
