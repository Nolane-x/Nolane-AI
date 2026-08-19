from __future__ import annotations
import itertools
from dataclasses import asdict
from typing import Callable
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r268_adaptive_causal_basis import synthesize_adaptive_causal_basis


def run_external_transfer(external_callable:Callable,*,source_id:str,source_version:str)->dict[str,object]:
    if not callable(external_callable): raise TypeError('external_callable must be callable')
    fields=('a','b','c','d');source_calls=0
    def oracle(row):
        nonlocal source_calls
        source_calls+=1
        matrix=[[float(row['a']),float(row['b'])],[float(row['c']),float(row['d'])]]
        return float(external_callable(matrix))

    # Discovery and validation deliberately occupy disjoint value domains.
    # With the only intervention anchor fixed at 0.0, every discovery oracle
    # query (base or intervened) therefore remains semantically disjoint from
    # every validation oracle query.  Validation is held out at the actual
    # oracle-input level, not merely by row index.
    discovery_values=(-2.0,-1.0,1.0,2.0)
    validation_values=(3.0,4.0,5.0,6.0)
    discovery_rows=tuple(itertools.product(discovery_values,repeat=4))
    validation_rows=tuple(itertools.product(validation_values,repeat=4))
    discovery=discovery_rows[:220]
    validation=validation_rows[:24]
    terminal=((101.0,103.0,107.0,109.0),(-113.0,127.0,131.0,137.0),(139.0,-149.0,151.0,157.0),(163.0,167.0,-173.0,179.0),(-181.0,191.0,193.0,197.0),(199.0,-211.0,223.0,-227.0))
    def contexts(raw): return tuple(dict(zip(fields,row,strict=True)) for row in raw)
    need=OperatorInventionNeed('R2.68 external determinant causal basis',fields,'out',constants=(0.0,1.0,-1.0,2.0),max_depth=5,max_candidates=200_000)
    receipt=synthesize_adaptive_causal_basis(
        oracle,fields,need,contexts(discovery),contexts(validation),terminal_contexts=contexts(terminal),
        intervention_anchor_values=(0.0,),intervention_arity=1,max_basis_size=4,
        composition_constants=(0.0,1.0,-1.0,2.0),composition_max_depth=5,
        composition_max_candidates_per_basis=50_000,max_composition_candidates_total=200_000,
        composition_beam_width=256,probe_constants=(0.0,1.0,-1.0,2.0),probe_max_depth=5,
        probe_max_candidates=60_000,probe_beam_width=256)
    lower_basis_certificates=[asdict(cert) for cert in receipt.structure.lower_basis_certificates]
    necessity_certificates=[asdict(cert) for cert in receipt.structure.necessity_certificates]
    passed=(
        receipt.passed
        and receipt.selected_basis_size==2
        and receipt.globally_minimal
        and receipt.structure.legal_interventions==4
        and receipt.structure.semantic_profiles==4
        and receipt.structure.proof_ledger_complete
        and receipt.structure.lower_basis_count==4
        and receipt.structure.lower_basis_certified==4
        and receipt.structure.lower_basis_inconclusive==0
        and len(lower_basis_certificates)==receipt.structure.lower_basis_certified
        and len(necessity_certificates)==2
        and all(row['basis_cardinality']==1 for row in lower_basis_certificates)
        and all(row['proof_kind']=='public_basis_target_collision' for row in lower_basis_certificates)
        and all(row['proof_kind']=='public_target_collision' for row in necessity_certificates)
        and receipt.false_accepts==0
        and receipt.final_validation_exact==receipt.final_validation_cases==len(terminal)
        and receipt.terminal_probe_validation_exact==receipt.terminal_probe_validation_cases==len(terminal)*2
        and receipt.oracle_calls_total==source_calls
    )
    return {
        'milestone':'R2.68','capability':'proof-carrying-adaptive-causal-basis','passed':passed,
        'source_id':str(source_id),'source_version':str(source_version),'source_exposure':'io_only',
        'discovery_validation_oracle_query_disjoint':True,
        'selected_basis_size':receipt.selected_basis_size,'globally_minimal':receipt.globally_minimal,
        'legal_interventions':receipt.structure.legal_interventions,'semantic_profiles':receipt.structure.semantic_profiles,
        'necessity_certificate_sizes':sorted({c.subset_cardinality for c in receipt.structure.necessity_certificates}),
        'necessity_certificate_count':len(necessity_certificates),'necessity_certificates':necessity_certificates,
        'lower_basis_count':receipt.structure.lower_basis_count,'lower_basis_certified':receipt.structure.lower_basis_certified,
        'lower_basis_inconclusive':receipt.structure.lower_basis_inconclusive,'lower_basis_universe_digest':receipt.structure.lower_basis_universe_digest,
        'lower_basis_certificate_count':len(lower_basis_certificates),'lower_basis_certificates':lower_basis_certificates,
        'proof_ledger_complete':receipt.structure.proof_ledger_complete,
        'terminal_cases':receipt.final_validation_cases,'terminal_exact':receipt.final_validation_exact,
        'terminal_probe_cases':receipt.terminal_probe_validation_cases,'terminal_probe_exact':receipt.terminal_probe_validation_exact,
        'false_accepts':receipt.false_accepts,'oracle_calls_total':receipt.oracle_calls_total,
        'source_calls_observed':source_calls,'oracle_accounting_exact':receipt.oracle_calls_total==source_calls,
        'trainable_parameter_count':0,
    }
