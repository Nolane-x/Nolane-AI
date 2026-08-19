from __future__ import annotations

from typing import Callable, Mapping, Sequence

from .r256_operator_invention import OperatorInventionNeed
from .r258_intervention_discovery import PositionalSchema, enumerate_interventions
from ._r268_proof import (
    build_basis_collision_certificate,
    build_public_target_collision_certificate,
    verify_basis_collision_certificate,
    verify_necessity_certificate,
)
from ._r268_runtime import (
    context_key as _context_key,
    derive_anchors as _derive_anchors,
    discover_adaptive_causal_basis as _runtime_discover_adaptive_causal_basis,
    synthesize_adaptive_causal_basis as _runtime_synthesize_adaptive_causal_basis,
)
from ._r268_types import AdaptiveCausalBasisCandidate,AdaptiveCausalBasisReceipt,AdaptiveCausalBasisStructureReceipt,BasisCollisionCertificate,NecessityCertificate


def _assert_cross_phase_oracle_query_disjointness(
    ordered_field_names: Sequence[str],
    anchor_values: Sequence[float],
    discovery_contexts: Sequence[Mapping[str, object]],
    validation_contexts: Sequence[Mapping[str, object]],
    *,
    context_validator: Callable[[Mapping[str, object]], bool] | None,
    intervention_arity: int,
) -> None:
    """Validate the complete discovery/validation oracle-query authority pre-call.

    Before the oracle is touched, materialize the semantic inputs that the
    runtime would actually query: every base context plus every query from each
    legal intervention profile.  Validation evidence must satisfy two stronger
    conditions than mere row-level holdout:

    * every validation oracle input is semantically unique within validation;
    * no validation oracle input was already present in discovery.

    This prevents repeated validation observations from inflating evidence and
    keeps validation genuinely fresh at the oracle-input level.
    """
    schema = PositionalSchema(tuple(map(str, ordered_field_names)))
    discovery = tuple(dict(row) for row in discovery_contexts)
    validation = tuple(dict(row) for row in validation_contexts)
    if not discovery or not validation:
        return

    # Preserve the runtime's base-context authority. If a base row is invalid,
    # let the runtime raise its established base-context error rather than
    # replacing that contract with an overlap/uniqueness error.
    for row in (*discovery, *validation):
        schema.to_canonical_context(row)
        if context_validator is not None and not bool(context_validator(row)):
            return

    discovery_keys = {_context_key(schema, row) for row in discovery}
    validation_query_keys = [_context_key(schema, row) for row in validation]
    specs = enumerate_interventions(
        schema.field_names,
        tuple(map(float, anchor_values)),
        arity=int(intervention_arity),
    )
    for spec in specs:
        discovery_queries = tuple(spec.apply(row, schema.field_names) for row in discovery)
        validation_queries = tuple(spec.apply(row, schema.field_names) for row in validation)
        if context_validator is not None and any(
            not bool(context_validator(row))
            for row in (*discovery_queries, *validation_queries)
        ):
            # The private runtime skips this entire intervention spec, so none
            # of these contexts belongs to either actually-used query phase.
            continue
        discovery_keys.update(_context_key(schema, row) for row in discovery_queries)
        validation_query_keys.extend(_context_key(schema, row) for row in validation_queries)

    validation_keys = set(validation_query_keys)
    if len(validation_keys) != len(validation_query_keys):
        raise ValueError(
            'validation oracle query inputs must be semantically unique '
            f'(duplicate_count={len(validation_query_keys) - len(validation_keys)})'
        )

    overlap = discovery_keys & validation_keys
    if overlap:
        raise ValueError(
            'discovery and validation oracle query inputs must be semantically disjoint '
            f'(overlap_count={len(overlap)})'
        )


def discover_adaptive_causal_basis(
    oracle: Callable[[Mapping[str, object]], object],
    ordered_field_names: Sequence[str],
    anchor_values: Sequence[float],
    discovery_contexts: Sequence[Mapping[str, object]],
    validation_contexts: Sequence[Mapping[str, object]],
    *,
    context_validator: Callable[[Mapping[str, object]], bool] | None = None,
    intervention_arity: int = 1,
    max_basis_size: int = 4,
    composition_constants: Sequence[object] = (0.0, 2.0),
    composition_max_depth: int = 5,
    composition_max_candidates_per_basis: int = 30_000,
    max_composition_candidates_total: int = 160_000,
    composition_beam_width: int = 192,
) -> AdaptiveCausalBasisStructureReceipt:
    if callable(oracle):
        _assert_cross_phase_oracle_query_disjointness(
            ordered_field_names,
            anchor_values,
            discovery_contexts,
            validation_contexts,
            context_validator=context_validator,
            intervention_arity=intervention_arity,
        )
    return _runtime_discover_adaptive_causal_basis(
        oracle,
        ordered_field_names,
        anchor_values,
        discovery_contexts,
        validation_contexts,
        context_validator=context_validator,
        intervention_arity=intervention_arity,
        max_basis_size=max_basis_size,
        composition_constants=composition_constants,
        composition_max_depth=composition_max_depth,
        composition_max_candidates_per_basis=composition_max_candidates_per_basis,
        max_composition_candidates_total=max_composition_candidates_total,
        composition_beam_width=composition_beam_width,
    )


def synthesize_adaptive_causal_basis(
    oracle: Callable[[Mapping[str, object]], object],
    ordered_field_names: Sequence[str],
    program_need: OperatorInventionNeed,
    discovery_contexts: Sequence[Mapping[str, object]],
    validation_contexts: Sequence[Mapping[str, object]],
    *,
    terminal_contexts: Sequence[Mapping[str, object]],
    context_validator: Callable[[Mapping[str, object]], bool] | None = None,
    intervention_anchor_values: Sequence[float] | None = None,
    intervention_arity: int = 1,
    max_basis_size: int = 4,
    composition_constants: Sequence[object] = (0.0, 2.0),
    composition_max_depth: int = 5,
    composition_max_candidates_per_basis: int = 30_000,
    max_composition_candidates_total: int = 160_000,
    composition_beam_width: int = 192,
    probe_constants: Sequence[object] = (0.0,),
    probe_max_depth: int = 5,
    probe_max_candidates: int = 50_000,
    probe_beam_width: int = 192,
) -> AdaptiveCausalBasisReceipt:
    fields = tuple(map(str, ordered_field_names))
    if (
        callable(oracle)
        and isinstance(program_need, OperatorInventionNeed)
        and set(fields) == set(program_need.field_names)
        and bool(tuple(terminal_contexts))
    ):
        anchors = (
            tuple(map(float, intervention_anchor_values))
            if intervention_anchor_values is not None
            else _derive_anchors(program_need, int(intervention_arity))
        )
        _assert_cross_phase_oracle_query_disjointness(
            fields,
            anchors,
            discovery_contexts,
            validation_contexts,
            context_validator=context_validator,
            intervention_arity=intervention_arity,
        )
    return _runtime_synthesize_adaptive_causal_basis(
        oracle,
        ordered_field_names,
        program_need,
        discovery_contexts,
        validation_contexts,
        terminal_contexts=terminal_contexts,
        context_validator=context_validator,
        intervention_anchor_values=intervention_anchor_values,
        intervention_arity=intervention_arity,
        max_basis_size=max_basis_size,
        composition_constants=composition_constants,
        composition_max_depth=composition_max_depth,
        composition_max_candidates_per_basis=composition_max_candidates_per_basis,
        max_composition_candidates_total=max_composition_candidates_total,
        composition_beam_width=composition_beam_width,
        probe_constants=probe_constants,
        probe_max_depth=probe_max_depth,
        probe_max_candidates=probe_max_candidates,
        probe_beam_width=probe_beam_width,
    )


__all__=[
    'NecessityCertificate','BasisCollisionCertificate','AdaptiveCausalBasisCandidate','AdaptiveCausalBasisStructureReceipt','AdaptiveCausalBasisReceipt',
    'build_basis_collision_certificate','verify_basis_collision_certificate','build_public_target_collision_certificate','verify_necessity_certificate',
    'discover_adaptive_causal_basis','synthesize_adaptive_causal_basis',
]
