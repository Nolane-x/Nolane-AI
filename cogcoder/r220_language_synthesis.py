from __future__ import annotations

from dataclasses import dataclass

from .r220_operator_language import (
    OperatorProgram,
    canonical_operator_id,
    operator_cost,
    operator_signature,
)


@dataclass(frozen=True)
class OperatorProposal:
    program: OperatorProgram
    operator_id: str
    mdl_cost: int


def _primitives(width: int) -> tuple[OperatorProgram, ...]:
    rows: list[OperatorProgram] = [OperatorProgram.identity()]
    for mask_int in range(1, 1 << width):
        mask = tuple((mask_int >> i) & 1 for i in range(width))
        rows.append(OperatorProgram.xor_mask(mask))
    for k in range(1, width):
        rows.append(OperatorProgram.rotate(k))
    for target in range(width):
        for source in range(width):
            if target != source:
                rows.append(OperatorProgram.shear_xor(target, source))
    # Small atomic transpositions; richer permutations can be composed.
    for i in range(width - 1):
        p = list(range(width))
        p[i], p[i + 1] = p[i + 1], p[i]
        rows.append(OperatorProgram.permute(tuple(p)))
    return tuple(rows)


def _proposal(program: OperatorProgram, width: int) -> OperatorProposal:
    return OperatorProposal(program, canonical_operator_id(program, width), operator_cost(program))


def synthesize_operator_proposals(width: int, *, max_nodes: int, primitive_budget: int) -> tuple[OperatorProposal, ...]:
    width, max_nodes, primitive_budget = int(width), int(max_nodes), int(primitive_budget)
    if width <= 0 or max_nodes < 0 or primitive_budget <= 0:
        raise ValueError('invalid synthesis budget')
    primitives = _primitives(width)[:primitive_budget]
    by_sig: dict[tuple, OperatorProposal] = {}

    identity = _proposal(OperatorProgram.identity(), width)
    by_sig[operator_signature(identity.program, width)] = identity
    frontier = [identity.program]

    for depth in range(1, max_nodes + 1):
        next_frontier: list[OperatorProgram] = []
        # Depth is exact number of non-identity primitives in composition.
        bases = [OperatorProgram.identity()] if depth == 1 else frontier
        for base in bases:
            for primitive in primitives:
                if primitive.op == 'identity':
                    continue
                program = OperatorProgram.compose(base, primitive)
                if operator_cost(program) != depth:
                    continue
                sig = operator_signature(program, width)
                candidate = _proposal(program, width)
                old = by_sig.get(sig)
                if old is None or (candidate.mdl_cost, repr(candidate.program)) < (old.mdl_cost, repr(old.program)):
                    by_sig[sig] = candidate
                    next_frontier.append(program)
        frontier = next_frontier
        if not frontier:
            break

    return tuple(sorted(by_sig.values(), key=lambda row: (row.mdl_cost, row.operator_id)))
