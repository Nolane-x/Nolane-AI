from __future__ import annotations
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r268_adaptive_causal_basis import synthesize_adaptive_causal_basis

FIELDS=('a','b')

def _ctx(rows):
    return tuple(dict(zip(FIELDS,row,strict=True)) for row in rows)

def _need():
    return OperatorInventionNeed('R2.68 terminal probe authority',FIELDS,'out',constants=(0.0,2.0),max_depth=5,max_candidates=100_000)

def _solve(oracle, *, context_validator=None):
    return synthesize_adaptive_causal_basis(
        oracle,FIELDS,_need(),
        _ctx(((-2,-2),(-2,-1),(-1,-2),(1,3),(4,-2),(5,7))),
        _ctx(((2,5),(-3,6),(8,-4))),
        terminal_contexts=_ctx(((101,103),(-109,113),(127,-131))),
        context_validator=context_validator,
        intervention_anchor_values=(0.0,),intervention_arity=1,max_basis_size=2,
        composition_constants=(0.0,2.0),composition_max_depth=5,
        composition_max_candidates_per_basis=30_000,max_composition_candidates_total=160_000,
        composition_beam_width=192,probe_constants=(0.0,2.0),probe_max_depth=5,
        probe_max_candidates=50_000,probe_beam_width=192,
    )

def test_terminal_probe_mismatch_stops_before_final_authority() -> None:
    def oracle(row):
        a=float(row['a']);b=float(row['b']);value=a+b
        if (a==0.0 or b==0.0) and max(abs(a),abs(b))>100.0:
            return value+1.0
        return value
    receipt=_solve(oracle)
    assert receipt.passed is False
    assert receipt.reason == 'terminal_probe_validation_failed'
    assert receipt.terminal_probe_validation_cases == 1
    assert receipt.terminal_probe_validation_exact == 0
    assert receipt.final_validation_cases == 0
    assert receipt.final_validation_exact == 0


def test_terminal_probe_preoracle_context_rejection_does_not_count_observation() -> None:
    oracle_calls=0
    def oracle(row):
        nonlocal oracle_calls
        oracle_calls+=1
        return float(row['a'])+float(row['b'])
    def validator(row):
        a=float(row['a']);b=float(row['b'])
        return not ((a==0.0 or b==0.0) and max(abs(a),abs(b))>100.0)

    receipt=_solve(oracle,context_validator=validator)

    assert receipt.passed is False
    assert receipt.reason == 'terminal_probe_context_rejected'
    assert receipt.terminal_probe_validation_cases == 0
    assert receipt.terminal_probe_validation_exact == 0
    assert receipt.final_validation_cases == 0
    assert receipt.final_validation_exact == 0
    assert receipt.oracle_calls_total == oracle_calls
