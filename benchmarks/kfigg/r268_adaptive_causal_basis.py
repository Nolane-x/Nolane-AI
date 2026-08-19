from __future__ import annotations
from dataclasses import asdict
from typing import Callable,Mapping
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r268_adaptive_causal_basis import synthesize_adaptive_causal_basis

Case = tuple[str, tuple[str,...], Callable[[Mapping[str,object]],object], tuple[tuple[float,...],...], tuple[tuple[float,...],...], tuple[tuple[float,...],...], int]

def _contexts(fields, rows): return tuple(dict(zip(fields,row,strict=True)) for row in rows)
def _need(label,fields): return OperatorInventionNeed(label,fields,'out',constants=(0.0,2.0),max_depth=5,max_candidates=120_000)
def _solve(case:Case):
    name,fields,oracle,discovery,validation,terminal,expected_size=case
    receipt=synthesize_adaptive_causal_basis(
        oracle,fields,_need(name,fields),_contexts(fields,discovery),_contexts(fields,validation),terminal_contexts=_contexts(fields,terminal),
        intervention_anchor_values=(0.0,),intervention_arity=1,max_basis_size=4,
        composition_constants=(0.0,2.0),composition_max_depth=5,composition_max_candidates_per_basis=30_000,
        max_composition_candidates_total=160_000,composition_beam_width=192,probe_constants=(0.0,2.0),probe_max_depth=5,
        probe_max_candidates=50_000,probe_beam_width=192)
    necessity=[asdict(cert) for cert in receipt.structure.necessity_certificates]
    lower=[asdict(cert) for cert in receipt.structure.lower_basis_certificates]
    return {
        'name':name,'passed':receipt.passed,'selected_basis_size':receipt.selected_basis_size,
        'expected_basis_size':expected_size,'globally_minimal':receipt.globally_minimal,
        'reason':receipt.reason,'false_accepts':receipt.false_accepts,
        'probe_validation_cases':receipt.probe_validation_cases,'probe_validation_exact':receipt.probe_validation_exact,
        'terminal_probe_validation_cases':receipt.terminal_probe_validation_cases,'terminal_probe_validation_exact':receipt.terminal_probe_validation_exact,
        'final_validation_cases':receipt.final_validation_cases,'final_validation_exact':receipt.final_validation_exact,
        'necessity_certificate_sizes':sorted({c.subset_cardinality for c in receipt.structure.necessity_certificates}),
        'necessity_certificate_count':len(necessity),'necessity_certificates':necessity,
        'lower_basis_count':receipt.structure.lower_basis_count,
        'lower_basis_certified':receipt.structure.lower_basis_certified,
        'lower_basis_inconclusive':receipt.structure.lower_basis_inconclusive,
        'lower_basis_certificate_count':len(lower),'lower_basis_certificates':lower,
        'lower_basis_universe_digest':receipt.structure.lower_basis_universe_digest,
        'proof_ledger_complete':receipt.structure.proof_ledger_complete,
        'oracle_calls_total':receipt.oracle_calls_total,
    }

def _cases()->tuple[Case,...]:
    f1=('a','b','c')
    def o1(r): return float(r['a'])*float(r['b'])
    f2=('a','b')
    def o2(r): return float(r['a'])+float(r['b'])
    f3=('a','b','c')
    def o3(r):
        a,b,c=(float(r[x]) for x in f3);return a*b+b*c+c*a
    f4=('a','b','c','d')
    def o4(r):
        a,b,c,d=(float(r[x]) for x in f4);return a*b+a*c+a*d+b*c+b*d+c*d
    return (
        ('one-probe-nuisance-rejection',f1,o1,((1,2,3),(2,3,4),(-2,5,7),(4,-3,9),(5,2,11),(-3,-2,13)),((6,7,15),(-5,4,17),(8,-2,19)),((101,103,107),(-109,113,127),(131,-137,139)),0),
        ('two-probe-sum',f2,o2,((-2,-2),(-2,-1),(-1,-2),(1,3),(4,-2),(5,7)),((2,5),(-3,6),(8,-4)),((101,103),(-109,113),(127,-131)),2),
        ('three-probe-triangle',f3,o3,((-2,-2,-2),(-2,-2,-1),(-2,-2,0),(-2,-1,-2),(-2,-1,0),(-2,0,-2),(-2,0,-1),(-1,-2,-2),(0,-2,-2),(0,-2,-1),(1,2,3),(4,-3,2),(5,2,-4)),((3,5,7),(-5,4,6),(8,-2,9)),((101,103,107),(-109,113,127),(131,-137,139)),3),
        ('four-probe-complete-pairwise',f4,o4,((-2,-2,-2,-2),(-2,-2,-2,-1),(-2,-2,-2,2),(-2,-2,-1,-2),(-2,-2,-1,2),(-2,-2,2,-2),(-2,-2,2,-1),(-2,-2,2,2),(-2,-1,-2,-2),(-2,-1,-2,2),(-2,-1,2,2),(-2,2,-2,-2),(-2,2,-2,-1),(-1,-2,-2,-2),(1,2,3,4),(5,-3,2,7),(-4,6,-2,3)),((3,5,7,11),(-5,4,6,-3),(8,-2,9,10)),((101,103,107,109),(-113,127,131,137),(139,-149,151,157)),4),
    )

def run_benchmark()->dict[str,object]:
    results=[_solve(case) for case in _cases()]
    selected=[row['selected_basis_size'] for row in results]
    false_accepts=sum(int(row['false_accepts']) for row in results)
    adaptive_selected=selected[1:]
    one_probe_nuisance_rejected=(
        results[0]['passed'] is False
        and results[0]['selected_basis_size']==0
        and results[0]['false_accepts']==0
    )
    expected_proof_counts=[0,2,6,14]
    complete_minimality_ledgers=results[0]['proof_ledger_complete'] is False and all(row['proof_ledger_complete'] is True for row in results[1:])
    replayable_global_ledgers=[row['lower_basis_certificate_count'] for row in results]==expected_proof_counts
    complete_local_ledgers=[row['necessity_certificate_count'] for row in results]==expected_proof_counts
    gates=[
        one_probe_nuisance_rejected,
        all(row['passed'] for row in results[1:]),
        selected==[0,2,3,4],
        adaptive_selected==[2,3,4],
        results[0]['globally_minimal'] is False,
        all(row['globally_minimal'] is True for row in results[1:]),
        [row['lower_basis_count'] for row in results]==expected_proof_counts,
        [row['lower_basis_certified'] for row in results]==expected_proof_counts,
        all(row['lower_basis_inconclusive']==0 for row in results),
        replayable_global_ledgers,
        complete_local_ledgers,
        all(all(cert['proof_kind']=='public_basis_target_collision' for cert in row['lower_basis_certificates']) for row in results[1:]),
        all(all(cert['proof_kind']=='public_target_collision' for cert in row['necessity_certificates']) for row in results[1:]),
        complete_minimality_ledgers,
        all(row['probe_validation_exact']==row['probe_validation_cases'] for row in results),
        all(row['terminal_probe_validation_exact']==row['terminal_probe_validation_cases'] for row in results),
        all(row['final_validation_exact']==row['final_validation_cases'] for row in results),
        false_accepts==0,
    ]
    return {
        'milestone':'R2.68',
        'capability':'proof-carrying-adaptive-causal-basis',
        'cases':results,
        'selected_basis_sizes':selected,
        'adaptive_selected_basis_sizes':adaptive_selected,
        'one_probe_nuisance_rejected':one_probe_nuisance_rejected,
        'mixed_cardinality_exact':adaptive_selected==[2,3,4],
        'complete_minimality_ledgers':complete_minimality_ledgers,
        'replayable_global_ledgers':replayable_global_ledgers,
        'complete_local_ledgers':complete_local_ledgers,
        'false_accepts':false_accepts,
        'trainable_parameter_count':0,
        'all_gates_pass':all(gates),
    }
