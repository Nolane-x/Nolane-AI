from __future__ import annotations

import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .execution_types import AgentDecisionReceipt, ExecutionAction, ExecutionCounters, InferenceRequest
from .types import AgentIdentity, ContextCapsule, canonical_digest


class AgentInferenceBackend(Protocol):
    backend_id: str
    checkpoint_digest: str

    def decide(self, request: InferenceRequest) -> AgentDecisionReceipt: ...


class CognitiveStateEncoder:
    """Canonical bridge encoder. It binds organization state to a digest; it does not claim semantic neural alignment."""

    def __init__(self, *, version: str = 'organization-context-digest-v1') -> None:
        if not str(version).strip():
            raise ValueError('encoder version must be explicit')
        self.version = str(version)

    @staticmethod
    def capsule_payload(capsule: ContextCapsule) -> dict[str, Any]:
        return {
            'agent_id': capsule.agent_id,
            'task_id': capsule.task_id,
            'plan_version': capsule.plan_version,
            'since_event_id': capsule.since_event_id,
            'memories': [row.to_state() for row in capsule.memories],
            'event_delta': [row.to_state() for row in capsule.event_delta],
            'authoritative_artifacts': [[str(k), v] for k, v in capsule.authoritative_artifacts],
            'tools': list(capsule.tools),
            'external_cores': list(capsule.external_cores),
            'applicable_skill_ids': list(capsule.applicable_skill_ids),
            'identity_summary': [[str(k), str(v)] for k, v in capsule.identity_summary],
            'authority_boundary': list(capsule.authority_boundary),
            'semantic_delta_digest': capsule.semantic_delta_digest,
            'context_compilation_receipt_id': capsule.context_compilation_receipt_id,
            'context_budget_units': capsule.context_budget_units,
            'context_overload_ratio': capsule.context_overload_ratio,
            'stale_context_warnings': list(capsule.stale_context_warnings),
        }

    def build_request(
        self,
        *,
        identity: AgentIdentity,
        capsule: ContextCapsule,
        task_id: str,
        action_schema: Sequence[str],
        counters: ExecutionCounters,
        step_index: int,
        checkpoint_digest: str,
    ) -> InferenceRequest:
        if capsule.agent_id != identity.agent_id:
            raise ValueError('context capsule identity mismatch')
        if capsule.task_id not in {None, str(task_id)}:
            raise ValueError('context capsule task mismatch')
        schema = tuple(str(x) for x in action_schema if str(x).strip())
        if not schema:
            raise ValueError('action schema must be non-empty')
        return InferenceRequest(
            agent_id=identity.agent_id,
            neural_version=identity.neural_version,
            task_id=str(task_id),
            context_digest=canonical_digest(self.capsule_payload(capsule)),
            encoder_version=self.version,
            checkpoint_digest=str(checkpoint_digest),
            action_schema=schema,
            action_schema_digest=canonical_digest(list(schema)),
            counters=counters,
            step_index=int(step_index),
        )


class DeterministicFixtureBackend:
    """Replay/test backend. Not evidence of neural capability."""

    def __init__(
        self,
        *,
        actions: Sequence[ExecutionAction],
        checkpoint_digest: str = 'fixture-checkpoint-v1',
        backend_id: str = 'deterministic-fixture-v1',
    ) -> None:
        rows = tuple(actions)
        if not rows:
            raise ValueError('fixture backend requires at least one action')
        if not str(checkpoint_digest).strip() or not str(backend_id).strip():
            raise ValueError('fixture backend identity must be explicit')
        self.actions = rows
        self.checkpoint_digest = str(checkpoint_digest)
        self.backend_id = str(backend_id)

    def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
        if request.checkpoint_digest != self.checkpoint_digest:
            raise ValueError('request checkpoint digest does not match backend')
        if request.step_index >= len(self.actions):
            action = ExecutionAction.fail(reason='fixture action sequence exhausted')
        else:
            action = self.actions[request.step_index]
        return AgentDecisionReceipt.create(backend_id=self.backend_id, request=request, action=action)


class R23InferenceBackend:
    """Lazy adapter for the accepted R2.3 one-weight bundle.

    Loading is real and hash-gated. Action selection requires an explicit action catalog and uses a deterministic
    bridge projection into the accepted R2.3 tensor interface. That projection is plumbing evidence only; it is not
    a validated coding representation and must not be used as capability evidence without a separately verified
    semantic encoder.
    """

    backend_id = 'neural-r2.3-bridge-v1'

    def __init__(
        self,
        *,
        checkpoint_digest: str,
        modules: tuple[Any, ...],
        action_catalog: Mapping[str, ExecutionAction] | None = None,
    ) -> None:
        self.checkpoint_digest = str(checkpoint_digest)
        self._modules = modules
        self._action_catalog = dict(action_catalog or {})

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(block)
        return digest.hexdigest()

    @classmethod
    def from_checkpoint(
        cls,
        *,
        checkpoint_path: str | Path,
        metadata_path: str | Path,
        model_root: str | Path,
        action_catalog: Mapping[str, ExecutionAction] | None = None,
    ) -> 'R23InferenceBackend':
        checkpoint = Path(checkpoint_path)
        metadata_file = Path(metadata_path)
        if not checkpoint.is_file():
            raise FileNotFoundError(f'R2.3 checkpoint not found: {checkpoint}')
        metadata = json.loads(metadata_file.read_text(encoding='utf-8'))
        expected = str(metadata.get('one_weight_sha256', '')).strip().lower()
        if len(expected) != 64:
            raise ValueError('accepted R2.3 metadata lacks checkpoint digest')
        observed = cls._sha256(checkpoint)
        if observed != expected:
            raise ValueError(f'checkpoint digest mismatch: {observed} != {expected}')

        root = Path(model_root).resolve()
        root_text = str(root)
        added = root_text not in sys.path
        if added:
            sys.path.insert(0, root_text)
        try:
            module = importlib.import_module('r23.standalone')
            loader = getattr(module, 'load_r23_one_weight')
            loaded = tuple(loader(checkpoint))
        finally:
            if added and sys.path and sys.path[0] == root_text:
                sys.path.pop(0)
        return cls(checkpoint_digest=observed, modules=loaded, action_catalog=action_catalog)

    @staticmethod
    def _stream_floats(seed: str, count: int) -> list[float]:
        out: list[float] = []
        counter = 0
        while len(out) < count:
            raw = hashlib.sha256(f'{seed}:{counter}'.encode('utf-8')).digest()
            for index in range(0, len(raw), 4):
                value = int.from_bytes(raw[index:index + 4], 'big') / 0xFFFFFFFF
                out.append(value * 2.0 - 1.0)
                if len(out) == count:
                    break
            counter += 1
        return out

    def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
        if request.checkpoint_digest != self.checkpoint_digest:
            raise ValueError('request checkpoint digest does not match R2.3 backend')
        missing = [name for name in request.action_schema if name not in self._action_catalog]
        if missing:
            raise RuntimeError('R2.3 action catalog missing schema entries: ' + ', '.join(missing))
        if len(self._modules) < 5:
            raise RuntimeError('R2.3 loader did not return accepted module tuple')

        import torch

        reasoner = self._modules[4]
        actions = len(request.action_schema)
        seed = canonical_digest(request.payload())
        state = torch.tensor(self._stream_floats(seed + ':state', 128), dtype=torch.float32).reshape(1, 128)
        context = torch.tensor(self._stream_floats(seed + ':context', 64), dtype=torch.float32).reshape(1, 64)
        action_embeddings = torch.tensor(
            self._stream_floats(seed + ':actions', actions * 640), dtype=torch.float32,
        ).reshape(1, actions, 640)
        effects = torch.tensor(
            self._stream_floats(seed + ':effects', actions * 128), dtype=torch.float32,
        ).reshape(1, actions, 128)
        action_memory = torch.zeros((1, actions, 7), dtype=torch.float32)
        zeros = torch.zeros((1, actions), dtype=torch.float32)
        progress = torch.tensor([[min(1.0, request.counters.steps / max(1, request.counters.steps + 1))]], dtype=torch.float32)
        budget_fraction = torch.tensor([[1.0]], dtype=torch.float32)
        previous_feedback = torch.zeros((1, 3), dtype=torch.float32)
        with torch.no_grad():
            output = reasoner(
                state=state,
                context=context,
                action_embeddings=action_embeddings,
                parent_effects=effects,
                imagined_effects=effects,
                evidence_effects=effects,
                action_memory=action_memory,
                imagined_uncertainty=zeros,
                imagined_value=zeros,
                base_action_logits=zeros,
                progress=progress,
                budget_fraction=budget_fraction,
                previous_feedback=previous_feedback,
                base_stop_logit=torch.zeros((1,), dtype=torch.float32),
                base_success_probability=torch.full((1,), 0.5, dtype=torch.float32),
                reasoning_steps=1,
            )
            index = int(output['action_logits'].argmax(dim=-1).item())
        action_name = request.action_schema[index]
        return AgentDecisionReceipt.create(
            backend_id=self.backend_id,
            request=request,
            action=self._action_catalog[action_name],
            compute_units=1,
        )
