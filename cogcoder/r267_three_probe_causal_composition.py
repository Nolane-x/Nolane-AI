from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .r256_operator_dsl import Expr
from .r256_operator_invention import OperatorInventionNeed


@dataclass(frozen=True, slots=True)
class ThreeProbeStructureReceipt:
    passed: bool
    selected: object | None
    reason: str
    trainable_parameter_count: int = 0


@dataclass(frozen=True, slots=True)
class ThreeProbeCompositionReceipt:
    passed: bool
    structure: ThreeProbeStructureReceipt
    expression: Expr | None
    probe_expressions: tuple[Expr, ...]
    reason: str
    trainable_parameter_count: int = 0


def discover_three_probe_structure(
    oracle: Callable[[Mapping[str, object]], object],
    ordered_field_names: Sequence[str],
    anchor_values: Sequence[float],
    discovery_contexts: Sequence[Mapping[str, object]],
    validation_contexts: Sequence[Mapping[str, object]],
    **_kwargs: object,
) -> ThreeProbeStructureReceipt:
    raise NotImplementedError('R2.67 three-probe structure discovery is not implemented yet')


def synthesize_three_probe_causal_program(
    oracle: Callable[[Mapping[str, object]], object],
    ordered_field_names: Sequence[str],
    program_need: OperatorInventionNeed,
    discovery_contexts: Sequence[Mapping[str, object]],
    validation_contexts: Sequence[Mapping[str, object]],
    *,
    terminal_contexts: Sequence[Mapping[str, object]],
    **_kwargs: object,
) -> ThreeProbeCompositionReceipt:
    raise NotImplementedError('R2.67 three-probe program synthesis is not implemented yet')


__all__ = [
    'ThreeProbeStructureReceipt',
    'ThreeProbeCompositionReceipt',
    'discover_three_probe_structure',
    'synthesize_three_probe_causal_program',
]
