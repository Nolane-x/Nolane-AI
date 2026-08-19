from __future__ import annotations
import hashlib,itertools,json,math
from typing import Callable,Mapping,Sequence
from .r256_operator_dsl import Expr,evaluate_expr,expr_digest
from .r256_operator_invention import OperatorExample,OperatorInventionNeed
from .r258_intervention_discovery import PositionalSchema,enumerate_interventions
from ._r268_proof import build_public_target_collision_certificate
from ._r268_search import equivalent,evaluate_vector,finite_json_value,rewrite_with_mapping,semantic_key,synthesize_variable_expression,used_fields
from ._r268_types import AdaptiveCausalBasisCandidate,AdaptiveCausalBasisReceipt,AdaptiveCausalBasisStructureReceipt,InterventionProfile,NecessityCertificate

def context_key(schema:PositionalSchema,context:Mapping[str,object])->str:
    canonical=schema.to_canonical_context(context);return semantic_key(tuple(canonical[f] for f in schema.canonical_fields))

def basis_shared_positions(schema:PositionalSchema,profiles:Sequence[InterventionProfile])->tuple[int,...]:
    fixed={p for profile in profiles for p,_ in profile.intervention.bindings};return tuple(i for i in range(len(schema.field_names)) if i not in fixed)

def composition_examples(schema:PositionalSchema,contexts:Sequence[Mapping[str,object]],targets:Sequence[object],profiles:Sequence[InterventionProfile],shared_positions:Sequence[int])->tuple[OperatorExample,...]:
    out=[]
    for index,(context,expected) in enumerate(zip(contexts,targets,strict=True)):
        canonical=schema.to_canonical_context(context);row={}
        for local,profile in enumerate(profiles):row[f'__p{local}']=(profile.discovery_outputs+profile.validation_outputs)[index]
        for pos in shared_positions:row[schema.canonical_fields[pos]]=canonical[schema.canonical_fields[pos]]
        out.append(OperatorExample(f'ctx:{index}',row,expected))
    return tuple(out)

def _empty_structure(reason:str,*,oracle_calls:int=0,learning_query_keys:frozenset[str]=frozenset(),validation_targets:tuple[object,...]=())->AdaptiveCausalBasisStructureReceipt:
    return AdaptiveCausalBasisStructureReceipt(False,None,0,False,(),(),0,0,0,0,0,oracle_calls,0,reason,learning_query_keys,validation_targets)

def discover_adaptive_causal_basis(oracle:Callable[[Mapping[str,object]],object],ordered_field_names:Sequence[str],anchor_values:Sequence[float],discovery_contexts:Sequence[Mapping[str,object]],validation_contexts:Sequence[Mapping[str,object]],*,context_validator:Callable[[Mapping[str,object]],bool]|None=None,intervention_arity:int=1,max_basis_size:int=4,composition_constants:Sequence[object]=(0.0,2.0),composition_max_depth:int=5,composition_max_candidates_per_basis:int=30_000,max_composition_candidates_total:int=160_000,composition_beam_width:int=192)->AdaptiveCausalBasisStructureReceipt:
    if not callable(oracle):raise TypeError('oracle must be callable')
    schema=PositionalSchema(tuple(map(str,ordered_field_names)));discovery=tuple(dict(r) for r in discovery_contexts);validation=tuple(dict(r) for r in validation_contexts)
    if not discovery or not validation:raise ValueError('discovery_contexts and validation_contexts must be non-empty')
    for row in (*discovery,*validation):
        schema.to_canonical_context(row)
        if context_validator is not None and not bool(context_validator(row)):raise ValueError('base contexts must satisfy context_validator')
    max_basis_size=int(max_basis_size);per_basis=int(composition_max_candidates_per_basis);max_total=int(max_composition_candidates_total)
    if max_basis_size<1 or per_basis<1 or max_total<1:raise ValueError('basis size and candidate budgets must be positive')
    oracle_calls=0;queried=set()
    def tracked(context):
        nonlocal oracle_calls
        queried.add(context_key(schema,context));oracle_calls+=1;return finite_json_value(oracle(dict(context)))
    d_targets=[];v_targets=[]
    try:
        for row in discovery:d_targets.append(tracked(row))
        for row in validation:v_targets.append(tracked(row))
    except Exception as exc:return _empty_structure(f'oracle_error:{type(exc).__name__}:{exc}',oracle_calls=oracle_calls,learning_query_keys=frozenset(queried),validation_targets=tuple(v_targets))
    selection=discovery+validation;targets=tuple(d_targets+v_targets);specs=enumerate_interventions(schema.field_names,tuple(map(float,anchor_values)),arity=int(intervention_arity));profiles=[]
    for spec in specs:
        ad=tuple(spec.apply(r,schema.field_names) for r in discovery);av=tuple(spec.apply(r,schema.field_names) for r in validation)
        if context_validator is not None and any(not bool(context_validator(r)) for r in (*ad,*av)):continue
        dv=[];vv=[]
        try:
            for row in ad:dv.append(tracked(row))
            for row in av:vv.append(tracked(row))
        except Exception as exc:return AdaptiveCausalBasisStructureReceipt(False,None,0,False,(),(),len(profiles),len(profiles),len(specs),0,0,oracle_calls,0,f'oracle_error:{type(exc).__name__}:{exc}',frozenset(queried),tuple(v_targets))
        outputs=tuple(dv+vv)
        if len({semantic_key((v,)) for v in outputs})<2:continue
        sid=hashlib.sha256(semantic_key(outputs).encode()).hexdigest();profiles.append(InterventionProfile(spec,tuple(dv),tuple(vv),sid))
    dedup={}
    for profile in profiles:
        prev=dedup.get(profile.semantic_profile_id)
        if prev is None or profile.intervention.intervention_id<prev.intervention.intervention_id:dedup[profile.semantic_profile_id]=profile
    semantic_profiles=tuple(dedup[k] for k in sorted(dedup));max_basis_size=min(max_basis_size,len(semantic_profiles));total=0;bases_considered=0;certs=[];unresolved=[];lower_ledger=[]
    for k in range(1,max_basis_size+1):
        bases=list(itertools.combinations(semantic_profiles,k));bases.sort(key=lambda b:tuple(p.semantic_profile_id for p in b))
        for basis_index,basis in enumerate(bases):
            ids=tuple(p.semantic_profile_id for p in basis);shared=basis_shared_positions(schema,basis);fields=tuple(f'__p{i}' for i in range(k))+tuple(schema.canonical_fields[i] for i in shared);examples=composition_examples(schema,selection,targets,basis,shared)
            cert=build_public_target_collision_certificate(basis_semantic_profile_ids=ids,subset_semantic_profile_ids=ids,exposed_fields=fields,examples=examples)
            ledger_identity={'cardinality':k,'semantic_profile_ids':list(ids),'exposed_fields':list(fields)}
            if cert is not None:
                certs.append(cert);lower_ledger.append((k,ledger_identity,'collision_certified'));continue
            remaining=max_total-total
            if remaining<=0:
                unresolved.append(f'k{k}:{"|".join(ids)}:budget_exhausted');lower_ledger.append((k,ledger_identity,'inconclusive'));continue
            fair=max(1,remaining//max(1,len(bases)-basis_index));budget=min(per_basis,fair);bases_considered+=1
            search=synthesize_variable_expression(fields,tuple(f'__p{i}' for i in range(k)),tuple(composition_constants),examples,max_depth=int(composition_max_depth),max_candidates=budget,beam_width=int(composition_beam_width));total+=search.candidates_considered
            if not search.passed or search.expression is None:
                unresolved.append(f'k{k}:{"|".join(ids)}:{search.reason}');lower_ledger.append((k,ledger_identity,'inconclusive'));continue
            used=used_fields(search.expression);required={f'__p{i}' for i in range(k)}
            if not required<=set(used):
                unresolved.append(f'k{k}:{"|".join(ids)}:required_probe_omitted');lower_ledger.append((k,ledger_identity,'inconclusive'));continue
            values,_=evaluate_vector(search.expression,examples)
            if values is None:
                unresolved.append(f'k{k}:{"|".join(ids)}:evaluation_error');lower_ledger.append((k,ledger_identity,'inconclusive'));continue
            exact=sum(int(equivalent(a,b)) for a,b in zip(values,targets,strict=True))
            if exact!=len(targets):
                unresolved.append(f'k{k}:{"|".join(ids)}:selection_mismatch');lower_ledger.append((k,ledger_identity,'inconclusive'));continue
            candidate=AdaptiveCausalBasisCandidate(tuple(p.intervention for p in basis),tuple(basis),ids,k,shared,search.expression,expr_digest(search.expression),used,len(targets),exact,search.candidates_considered)
            lower_rows=[(cardinality,identity,status) for cardinality,identity,status in lower_ledger if cardinality<k]
            lower_unresolved=tuple(row for row in unresolved if any(row.startswith(f'k{s}:') for s in range(1,k)))
            lower_count=len(lower_rows);lower_certified=sum(int(status=='collision_certified') for _cardinality,_identity,status in lower_rows);lower_inconclusive=lower_count-lower_certified
            universe_payload=[identity for _cardinality,identity,_status in sorted(lower_rows,key=lambda row:(row[0],tuple(row[1]['semantic_profile_ids']),tuple(row[1]['exposed_fields'])))]
            universe_raw=json.dumps(universe_payload,sort_keys=True,separators=(',',':'),allow_nan=False)
            universe_digest=hashlib.sha256(universe_raw.encode()).hexdigest() if universe_payload else ''
            proof_complete=k>1 and lower_count>0 and lower_certified==lower_count and lower_inconclusive==0
            minimal=proof_complete;reason='adaptive_basis_discovered' if minimal else 'sufficient_but_minimality_inconclusive'
            return AdaptiveCausalBasisStructureReceipt(
                passed=True,selected=candidate,selected_basis_size=k,globally_minimal=minimal,necessity_certificates=tuple(certs),
                unresolved_lower_order=lower_unresolved,legal_interventions=len(profiles),semantic_profiles=len(semantic_profiles),
                intervention_candidates_considered=len(specs),bases_considered=bases_considered,composition_candidates_considered=total,
                oracle_calls=oracle_calls,false_accepts=0,reason=reason,learning_query_keys=frozenset(queried),validation_targets=tuple(v_targets),
                lower_basis_count=lower_count,lower_basis_certified=lower_certified,lower_basis_inconclusive=lower_inconclusive,
                lower_basis_universe_digest=universe_digest,proof_ledger_complete=proof_complete,
            )
    reason='basis_search_budget_exhausted' if total>=max_total else 'no_adaptive_basis'
    if unresolved:reason='necessity_certificate_missing'
    return AdaptiveCausalBasisStructureReceipt(False,None,0,False,tuple(certs),tuple(unresolved),len(profiles),len(semantic_profiles),len(specs),bases_considered,total,oracle_calls,0,reason,frozenset(queried),tuple(v_targets))

def derive_anchors(need:OperatorInventionNeed,arity:int)->tuple[float,...]:
    values=[]
    for raw in need.constants:
        if isinstance(raw,bool) or not isinstance(raw,(int,float)):continue
        v=float(raw)
        if math.isfinite(v) and v not in values:values.append(v)
    if 0.0 not in values:values.insert(0,0.0)
    while len(values)<int(arity):
        v=float(len(values))
        if v not in values:values.append(v)
    return tuple(values)

def synthesize_adaptive_causal_basis(oracle:Callable[[Mapping[str,object]],object],ordered_field_names:Sequence[str],program_need:OperatorInventionNeed,discovery_contexts:Sequence[Mapping[str,object]],validation_contexts:Sequence[Mapping[str,object]],*,terminal_contexts:Sequence[Mapping[str,object]],context_validator:Callable[[Mapping[str,object]],bool]|None=None,intervention_anchor_values:Sequence[float]|None=None,intervention_arity:int=1,max_basis_size:int=4,composition_constants:Sequence[object]=(0.0,2.0),composition_max_depth:int=5,composition_max_candidates_per_basis:int=30_000,max_composition_candidates_total:int=160_000,composition_beam_width:int=192,probe_constants:Sequence[object]=(0.0,),probe_max_depth:int=5,probe_max_candidates:int=50_000,probe_beam_width:int=192)->AdaptiveCausalBasisReceipt:
    if not callable(oracle):raise TypeError('oracle must be callable')
    if not isinstance(program_need,OperatorInventionNeed):raise TypeError('program_need must be OperatorInventionNeed')
    schema=PositionalSchema(tuple(map(str,ordered_field_names)))
    if set(schema.field_names)!=set(program_need.field_names):raise ValueError('ordered_field_names must match program_need fields')
    discovery=tuple(dict(r) for r in discovery_contexts);validation=tuple(dict(r) for r in validation_contexts);terminal=tuple(dict(r) for r in terminal_contexts)
    if not terminal:raise ValueError('terminal_contexts must be non-empty')
    anchors=tuple(map(float,intervention_anchor_values)) if intervention_anchor_values is not None else derive_anchors(program_need,int(intervention_arity))
    structure=discover_adaptive_causal_basis(oracle,schema.field_names,anchors,discovery,validation,context_validator=context_validator,intervention_arity=int(intervention_arity),max_basis_size=int(max_basis_size),composition_constants=tuple(composition_constants),composition_max_depth=int(composition_max_depth),composition_max_candidates_per_basis=int(composition_max_candidates_per_basis),max_composition_candidates_total=int(max_composition_candidates_total),composition_beam_width=int(composition_beam_width))
    if not structure.passed or structure.selected is None:return AdaptiveCausalBasisReceipt(False,structure,None,(),(),0,0,0,0,'structure_discovery_failed',0,False,0,0,structure.oracle_calls,0,0)
    selected=structure.selected;probe_c=[];probe_e=[];probe_counts=[];probe_cases=probe_exact=0
    for profile in selected.profiles:
        fixed={p for p,_ in profile.intervention.bindings};free=tuple(i for i in range(len(schema.field_names)) if i not in fixed);fields=tuple(schema.canonical_fields[i] for i in free)
        examples=[]
        for index,(context,expected) in enumerate(zip(discovery,profile.discovery_outputs,strict=True)):
            canonical=schema.to_canonical_context(context);examples.append(OperatorExample(f'probe:{index}',{schema.canonical_fields[p]:canonical[schema.canonical_fields[p]] for p in free},expected))
        probe=synthesize_variable_expression(fields,(),tuple(probe_constants),tuple(examples),max_depth=int(probe_max_depth),max_candidates=int(probe_max_candidates),beam_width=int(probe_beam_width));probe_counts.append(probe.candidates_considered)
        if not probe.passed or probe.expression is None:return AdaptiveCausalBasisReceipt(False,structure,None,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,0,0,'probe_synthesis_failed',selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls,0,0)
        canonical=probe.expression;external=schema.externalize_expr(canonical);probe_c.append(canonical);probe_e.append(external)
        for context,expected in zip(validation,profile.validation_outputs,strict=True):
            probe_cases+=1
            try:actual=finite_json_value(evaluate_expr(external,context))
            except (ArithmeticError,KeyError,TypeError,ValueError,OverflowError,ZeroDivisionError):actual=object()
            probe_exact+=int(equivalent(actual,expected))
    if probe_exact!=probe_cases:return AdaptiveCausalBasisReceipt(False,structure,None,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,0,0,'probe_validation_failed',selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls,0,0)
    expression=schema.externalize_expr(rewrite_with_mapping(selected.expression,{f'__p{i}':probe_c[i] for i in range(selected.basis_size)}));validation_exact=0
    for context,expected in zip(validation,structure.validation_targets,strict=True):
        try:actual=finite_json_value(evaluate_expr(expression,context))
        except (ArithmeticError,KeyError,TypeError,ValueError,OverflowError,ZeroDivisionError):actual=object()
        validation_exact+=int(equivalent(actual,expected))
    if validation_exact!=len(validation):return AdaptiveCausalBasisReceipt(False,structure,expression,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,0,0,'substituted_validation_failed',selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls,0,0)
    seen=set()
    for context in terminal:
        schema.to_canonical_context(context);key=context_key(schema,context)
        if key in structure.learning_query_keys:raise ValueError('terminal_contexts must be disjoint from all oracle query inputs used for learning')
        if key in seen:raise ValueError('terminal_contexts must be semantically unique')
        if context_validator is not None and not bool(context_validator(context)):raise ValueError('terminal contexts must satisfy context_validator')
        seen.add(key)
    terminal_calls=terminal_probe_cases=terminal_probe_exact=final_cases=final_exact=0
    def terminal_oracle(context):
        nonlocal terminal_calls
        terminal_calls+=1;return finite_json_value(oracle(dict(context)))
    try:
        for context in terminal:
            for index,profile in enumerate(selected.profiles):
                intervened=profile.intervention.apply(context,schema.field_names);key=context_key(schema,intervened);terminal_probe_cases+=1
                if key in structure.learning_query_keys or key in seen:raise ValueError('terminal intervention inputs must be disjoint from all prior evidence inputs')
                if context_validator is not None and not bool(context_validator(intervened)):raise RuntimeError('terminal intervention rejected')
                seen.add(key);expected=terminal_oracle(intervened);actual=finite_json_value(evaluate_expr(probe_e[index],context))
                if not equivalent(actual,expected):
                    return AdaptiveCausalBasisReceipt(False,structure,expression,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,final_cases,final_exact,'terminal_probe_validation_failed',selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls+terminal_calls,terminal_probe_cases,terminal_probe_exact)
                terminal_probe_exact+=1
            final_cases+=1;expected=terminal_oracle(context);actual=finite_json_value(evaluate_expr(expression,context));final_exact+=int(equivalent(actual,expected))
    except Exception:
        reason='terminal_probe_oracle_error' if final_cases==0 or terminal_probe_cases>terminal_probe_exact else 'final_terminal_oracle_error'
        return AdaptiveCausalBasisReceipt(False,structure,expression,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,final_cases,final_exact,reason,selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls+terminal_calls,terminal_probe_cases,terminal_probe_exact)
    if terminal_probe_exact!=terminal_probe_cases:return AdaptiveCausalBasisReceipt(False,structure,expression,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,final_cases,final_exact,'terminal_probe_validation_failed',selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls+terminal_calls,terminal_probe_cases,terminal_probe_exact)
    if final_exact!=final_cases:return AdaptiveCausalBasisReceipt(False,structure,expression,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,final_cases,final_exact,'final_validation_failed',selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls+terminal_calls,terminal_probe_cases,terminal_probe_exact)
    return AdaptiveCausalBasisReceipt(True,structure,expression,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,final_cases,final_exact,structure.reason,selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls+terminal_calls,terminal_probe_cases,terminal_probe_exact)
