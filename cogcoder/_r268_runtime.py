from __future__ import annotations
import hashlib,itertools,json,math
from typing import Callable,Mapping,Sequence
from .r256_operator_dsl import Expr,evaluate_expr,expr_digest
from .r256_operator_invention import OperatorExample,OperatorInventionNeed
from .r258_intervention_discovery import PositionalSchema,enumerate_interventions
from ._r268_proof import build_basis_collision_certificate,build_public_target_collision_certificate
from ._r268_search import equivalent,evaluate_vector,finite_json_value,rewrite_with_mapping,semantic_key,synthesize_variable_expression,used_fields
from ._r268_types import AdaptiveCausalBasisCandidate,AdaptiveCausalBasisReceipt,AdaptiveCausalBasisStructureReceipt,InterventionProfile,NecessityCertificate


def context_key(schema:PositionalSchema,context:Mapping[str,object])->str:
    canonical=schema.to_canonical_context(context);return semantic_key(tuple(canonical[f] for f in schema.canonical_fields))


def basis_shared_positions(schema:PositionalSchema,profiles:Sequence[InterventionProfile])->tuple[int,...]:
    fixed={p for profile in profiles for p,_ in profile.intervention.bindings};return tuple(i for i in range(len(schema.field_names)) if i not in fixed)


def _profile_proposal_key(profile:InterventionProfile)->tuple[str,str]:
    return semantic_key(profile.discovery_outputs),profile.intervention.intervention_id


def _profile_proposal_equivalence_key(profile:InterventionProfile)->tuple[tuple[int,...],str]:
    # Proposal scheduling is discovery-only. Authority identity remains bound
    # to the concrete intervention in InterventionProfile.semantic_profile_id.
    positions=tuple(position for position,_value in profile.intervention.bindings)
    return positions,semantic_key(profile.discovery_outputs)


def _canonicalize_proposal_basis(profiles:Sequence[InterventionProfile])->tuple[InterventionProfile,...]:
    # Probe slot assignment must not depend on the content-addressed ordering of
    # concrete authority identities. Sort first by discovery-only proposal class
    # and use intervention id only as a deterministic tie-break within one class.
    return tuple(sorted(
        tuple(profiles),
        key=lambda profile:(_profile_proposal_equivalence_key(profile),profile.intervention.intervention_id),
    ))


def _basis_proposal_equivalence_key(profiles:Sequence[InterventionProfile])->tuple[tuple[tuple[int,...],str],...]:
    canonical=_canonicalize_proposal_basis(profiles)
    return tuple(_profile_proposal_equivalence_key(profile) for profile in canonical)


def composition_examples(schema:PositionalSchema,contexts:Sequence[Mapping[str,object]],targets:Sequence[object],profiles:Sequence[InterventionProfile],shared_positions:Sequence[int],*,phase:str)->tuple[OperatorExample,...]:
    if phase not in {'discovery','validation'}:raise ValueError('phase must be discovery or validation')
    out=[]
    for index,(context,expected) in enumerate(zip(contexts,targets,strict=True)):
        canonical=schema.to_canonical_context(context);row={}
        for local,profile in enumerate(profiles):
            outputs=profile.discovery_outputs if phase=='discovery' else profile.validation_outputs
            row[f'__p{local}']=outputs[index]
        for pos in shared_positions:row[schema.canonical_fields[pos]]=canonical[schema.canonical_fields[pos]]
        out.append(OperatorExample(f'{phase}:{index}',row,expected))
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
    specs=enumerate_interventions(schema.field_names,tuple(map(float,anchor_values)),arity=int(intervention_arity));profiles=[]
    for spec in specs:
        ad=tuple(spec.apply(r,schema.field_names) for r in discovery);av=tuple(spec.apply(r,schema.field_names) for r in validation)
        if context_validator is not None and any(not bool(context_validator(r)) for r in (*ad,*av)):continue
        dv=[];vv=[]
        try:
            for row in ad:dv.append(tracked(row))
            for row in av:vv.append(tracked(row))
        except Exception as exc:return AdaptiveCausalBasisStructureReceipt(False,None,0,False,(),(),len(profiles),len(profiles),len(specs),0,0,oracle_calls,0,f'oracle_error:{type(exc).__name__}:{exc}',frozenset(queried),tuple(v_targets))
        discovery_outputs=tuple(dv);validation_outputs=tuple(vv)
        if all(equivalent(value,target) for value,target in zip(discovery_outputs,d_targets,strict=True)):continue
        if len({semantic_key((v,)) for v in discovery_outputs})<2:continue
        identity_payload={'discovery':semantic_key(discovery_outputs),'validation':semantic_key(validation_outputs)}
        identity_raw=json.dumps(identity_payload,sort_keys=True,separators=(',',':'))
        sid=hashlib.sha256(identity_raw.encode()).hexdigest();profiles.append(InterventionProfile(spec,discovery_outputs,validation_outputs,sid))
    dedup={}
    for profile in profiles:
        prev=dedup.get(profile.semantic_profile_id)
        if prev is None or profile.intervention.intervention_id<prev.intervention.intervention_id:dedup[profile.semantic_profile_id]=profile
    semantic_profiles=tuple(sorted(dedup.values(),key=_profile_proposal_key));max_basis_size=min(max_basis_size,len(semantic_profiles));total=0;bases_considered=0;unresolved=[];lower_ledger=[];lower_basis_certs=[]
    for k in range(1,max_basis_size+1):
        bases=[_canonicalize_proposal_basis(basis) for basis in itertools.combinations(semantic_profiles,k)]
        bases.sort(key=lambda basis:tuple((_profile_proposal_equivalence_key(profile),profile.intervention.intervention_id) for profile in basis))

        # Proof authority enumerates every concrete intervention basis. Proposal
        # search is a discovery-only computation and is reusable across bases
        # with exactly the same proposal-equivalence key. Every basis is first
        # canonicalized into proposal-slot order so cached expressions preserve
        # the same __p0..__p{k-1} meaning across concrete authority aliases.
        searchable_proposal_classes=set()
        for preview_basis in bases:
            preview_ids=tuple(p.semantic_profile_id for p in preview_basis)
            preview_shared=basis_shared_positions(schema,preview_basis)
            preview_fields=tuple(f'__p{i}' for i in range(k))+tuple(schema.canonical_fields[i] for i in preview_shared)
            preview_examples=composition_examples(schema,discovery,tuple(d_targets),preview_basis,preview_shared,phase='discovery')
            preview_cert=build_basis_collision_certificate(semantic_profile_ids=preview_ids,exposed_fields=preview_fields,examples=preview_examples)
            if preview_cert is None:
                searchable_proposal_classes.add(_basis_proposal_equivalence_key(preview_basis))
        attempted_proposal_classes=set();proposal_search_cache={}

        for basis_index,basis in enumerate(bases):
            ids=tuple(p.semantic_profile_id for p in basis);shared=basis_shared_positions(schema,basis);fields=tuple(f'__p{i}' for i in range(k))+tuple(schema.canonical_fields[i] for i in shared);examples=composition_examples(schema,discovery,tuple(d_targets),basis,shared,phase='discovery');validation_examples=composition_examples(schema,validation,tuple(v_targets),basis,shared,phase='validation')
            basis_cert=build_basis_collision_certificate(semantic_profile_ids=ids,exposed_fields=fields,examples=examples)
            ledger_identity={'cardinality':k,'semantic_profile_ids':list(ids),'exposed_fields':list(fields)}
            if basis_cert is not None:
                lower_basis_certs.append(basis_cert);lower_ledger.append((k,ledger_identity,'collision_certified'));continue
            proposal_class=_basis_proposal_equivalence_key(basis);bases_considered+=1
            if proposal_class in proposal_search_cache:
                search=proposal_search_cache[proposal_class]
            else:
                remaining=max_total-total
                if remaining<=0:
                    unresolved.append(f'k{k}:{"|".join(ids)}:budget_exhausted');lower_ledger.append((k,ledger_identity,'inconclusive'));continue
                pending_classes=searchable_proposal_classes-attempted_proposal_classes
                fair=max(1,remaining//max(1,len(pending_classes)));budget=min(per_basis,fair)
                attempted_proposal_classes.add(proposal_class)
                search=synthesize_variable_expression(fields,tuple(f'__p{i}' for i in range(k)),tuple(composition_constants),examples,max_depth=int(composition_max_depth),max_candidates=budget,beam_width=int(composition_beam_width))
                proposal_search_cache[proposal_class]=search;total+=search.candidates_considered
            if not search.passed or search.expression is None:
                unresolved.append(f'k{k}:{"|".join(ids)}:{search.reason}');lower_ledger.append((k,ledger_identity,'inconclusive'));continue
            used=used_fields(search.expression);required={f'__p{i}' for i in range(k)}
            if not required<=set(used):
                unresolved.append(f'k{k}:{"|".join(ids)}:required_probe_omitted');lower_ledger.append((k,ledger_identity,'inconclusive'));continue
            values,_=evaluate_vector(search.expression,examples)
            if values is None:
                unresolved.append(f'k{k}:{"|".join(ids)}:evaluation_error');lower_ledger.append((k,ledger_identity,'inconclusive'));continue
            exact=sum(int(equivalent(a,b)) for a,b in zip(values,d_targets,strict=True))
            if exact!=len(d_targets):
                unresolved.append(f'k{k}:{"|".join(ids)}:selection_mismatch');lower_ledger.append((k,ledger_identity,'inconclusive'));continue
            validation_values,_=evaluate_vector(search.expression,validation_examples)
            if validation_values is None:
                unresolved.append(f'k{k}:{"|".join(ids)}:composition_validation_error');lower_ledger.append((k,ledger_identity,'inconclusive'));continue
            validation_exact=sum(int(equivalent(a,b)) for a,b in zip(validation_values,v_targets,strict=True))
            if validation_exact!=len(v_targets):
                unresolved.append(f'k{k}:{"|".join(ids)}:composition_validation_failed');lower_ledger.append((k,ledger_identity,'inconclusive'));continue
            candidate=AdaptiveCausalBasisCandidate(tuple(p.intervention for p in basis),tuple(basis),ids,k,shared,search.expression,expr_digest(search.expression),used,len(d_targets),exact,len(v_targets),validation_exact,search.candidates_considered)
            selected_certs=[];local_certificate_missing=False
            for subset_size in range(1,k):
                for subset_indexes in itertools.combinations(range(k),subset_size):
                    subset_profiles=tuple(basis[index] for index in subset_indexes)
                    subset_ids=tuple(profile.semantic_profile_id for profile in subset_profiles)
                    subset_shared=basis_shared_positions(schema,subset_profiles)
                    subset_fields=tuple(f'__p{i}' for i in range(subset_size))+tuple(schema.canonical_fields[index] for index in subset_shared)
                    subset_examples=composition_examples(schema,discovery,tuple(d_targets),subset_profiles,subset_shared,phase='discovery')
                    subset_cert=build_public_target_collision_certificate(
                        basis_semantic_profile_ids=ids,
                        subset_semantic_profile_ids=subset_ids,
                        exposed_fields=subset_fields,
                        examples=subset_examples,
                    )
                    if subset_cert is None:
                        local_certificate_missing=True
                        break
                    selected_certs.append(subset_cert)
                if local_certificate_missing:break
            lower_rows=[(cardinality,identity,status) for cardinality,identity,status in lower_ledger if cardinality<k]
            lower_unresolved=tuple(row for row in unresolved if any(row.startswith(f'k{s}:') for s in range(1,k)))
            lower_count=len(lower_rows)
            selected_lower_certs=tuple(cert for cert in lower_basis_certs if cert.basis_cardinality<k)
            lower_certified=len(selected_lower_certs);lower_inconclusive=lower_count-lower_certified
            certificate_lookup={(cert.basis_cardinality,cert.semantic_profile_ids,cert.exposed_fields):cert.witness_digest for cert in selected_lower_certs}
            universe_payload=[]
            for cardinality,identity,status in sorted(lower_rows,key=lambda row:(row[0],tuple(row[1]['semantic_profile_ids']),tuple(row[1]['exposed_fields']))):
                key=(cardinality,tuple(identity['semantic_profile_ids']),tuple(identity['exposed_fields']))
                universe_payload.append({'identity':identity,'status':status,'witness_digest':certificate_lookup.get(key,'')})
            universe_raw=json.dumps(universe_payload,sort_keys=True,separators=(',',':'),allow_nan=False)
            universe_digest=hashlib.sha256(universe_raw.encode()).hexdigest() if universe_payload else ''
            global_proof_complete=k>1 and lower_count>0 and lower_certified==lower_count and lower_inconclusive==0 and all(row['witness_digest'] for row in universe_payload)
            expected_local_certificates=(1<<k)-2 if k>1 else 0
            local_proof_complete=k>1 and not local_certificate_missing and len(selected_certs)==expected_local_certificates
            minimal=global_proof_complete and local_proof_complete;reason='adaptive_basis_discovered' if minimal else 'sufficient_but_minimality_inconclusive'
            return AdaptiveCausalBasisStructureReceipt(
                passed=True,selected=candidate,selected_basis_size=k,globally_minimal=minimal,necessity_certificates=tuple(selected_certs),
                unresolved_lower_order=lower_unresolved,legal_interventions=len(profiles),semantic_profiles=len(semantic_profiles),
                intervention_candidates_considered=len(specs),bases_considered=bases_considered,composition_candidates_considered=total,
                oracle_calls=oracle_calls,false_accepts=0,reason=reason,learning_query_keys=frozenset(queried),validation_targets=tuple(v_targets),
                lower_basis_count=lower_count,lower_basis_certified=lower_certified,lower_basis_inconclusive=lower_inconclusive,
                lower_basis_universe_digest=universe_digest,proof_ledger_complete=global_proof_complete and local_proof_complete,
                lower_basis_certificates=selected_lower_certs,
            )
    reason='basis_search_budget_exhausted' if total>=max_total else 'no_adaptive_basis'
    if unresolved:reason='necessity_certificate_missing'
    return AdaptiveCausalBasisStructureReceipt(False,None,0,False,(),tuple(unresolved),len(profiles),len(semantic_profiles),len(specs),bases_considered,total,oracle_calls,0,reason,frozenset(queried),tuple(v_targets))


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
    for context in terminal:
        for index,profile in enumerate(selected.profiles):
            intervened=profile.intervention.apply(context,schema.field_names);key=context_key(schema,intervened)
            if key in structure.learning_query_keys or key in seen:
                return AdaptiveCausalBasisReceipt(False,structure,expression,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,final_cases,final_exact,'terminal_probe_evidence_overlap',selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls+terminal_calls,terminal_probe_cases,terminal_probe_exact)
            if context_validator is not None and not bool(context_validator(intervened)):
                return AdaptiveCausalBasisReceipt(False,structure,expression,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,final_cases,final_exact,'terminal_probe_context_rejected',selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls+terminal_calls,terminal_probe_cases,terminal_probe_exact)
            seen.add(key);terminal_probe_cases+=1
            try:expected=terminal_oracle(intervened)
            except Exception:
                return AdaptiveCausalBasisReceipt(False,structure,expression,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,final_cases,final_exact,'terminal_probe_oracle_error',selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls+terminal_calls,terminal_probe_cases,terminal_probe_exact)
            try:actual=finite_json_value(evaluate_expr(probe_e[index],context))
            except (ArithmeticError,KeyError,TypeError,ValueError,OverflowError,ZeroDivisionError):
                return AdaptiveCausalBasisReceipt(False,structure,expression,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,final_cases,final_exact,'terminal_probe_validation_failed',selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls+terminal_calls,terminal_probe_cases,terminal_probe_exact)
            if not equivalent(actual,expected):
                return AdaptiveCausalBasisReceipt(False,structure,expression,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,final_cases,final_exact,'terminal_probe_validation_failed',selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls+terminal_calls,terminal_probe_cases,terminal_probe_exact)
            terminal_probe_exact+=1
        final_cases+=1
        try:expected=terminal_oracle(context)
        except Exception:
            return AdaptiveCausalBasisReceipt(False,structure,expression,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,final_cases,final_exact,'final_terminal_oracle_error',selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls+terminal_calls,terminal_probe_cases,terminal_probe_exact)
        try:actual=finite_json_value(evaluate_expr(expression,context))
        except (ArithmeticError,KeyError,TypeError,ValueError,OverflowError,ZeroDivisionError):
            return AdaptiveCausalBasisReceipt(False,structure,expression,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,final_cases,final_exact,'final_validation_failed',selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls+terminal_calls,terminal_probe_cases,terminal_probe_exact)
        if not equivalent(actual,expected):
            return AdaptiveCausalBasisReceipt(False,structure,expression,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,final_cases,final_exact,'final_validation_failed',selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls+terminal_calls,terminal_probe_cases,terminal_probe_exact)
        final_exact+=1
    return AdaptiveCausalBasisReceipt(True,structure,expression,tuple(probe_e),tuple(probe_counts),probe_cases,probe_exact,final_cases,final_exact,structure.reason,selected.basis_size,structure.globally_minimal,0,0,structure.oracle_calls+terminal_calls,terminal_probe_cases,terminal_probe_exact)