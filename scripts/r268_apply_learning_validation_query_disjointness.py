from pathlib import Path

path = Path('cogcoder/_r268_runtime.py')
text = path.read_text()

old_budget = """    max_basis_size=int(max_basis_size);per_basis=int(composition_max_candidates_per_basis);max_total=int(max_composition_candidates_total)\n    if max_basis_size<1 or per_basis<1 or max_total<1:raise ValueError('basis size and candidate budgets must be positive')\n    oracle_calls=0;queried=set()\n"""
new_budget = """    max_basis_size=int(max_basis_size);per_basis=int(composition_max_candidates_per_basis);max_total=int(max_composition_candidates_total)\n    if max_basis_size<1 or per_basis<1 or max_total<1:raise ValueError('basis size and candidate budgets must be positive')\n\n    # Validation is authority evidence, not another view of learning evidence.\n    # Its complete oracle-input universe (base rows plus every legal\n    # intervention application that this routine would query) must therefore\n    # be semantically disjoint from the discovery oracle-input universe.\n    specs=enumerate_interventions(schema.field_names,tuple(map(float,anchor_values)),arity=int(intervention_arity))\n    prepared_specs=[]\n    discovery_query_keys={context_key(schema,row) for row in discovery}\n    validation_query_keys={context_key(schema,row) for row in validation}\n    for spec in specs:\n        ad=tuple(spec.apply(r,schema.field_names) for r in discovery);av=tuple(spec.apply(r,schema.field_names) for r in validation)\n        if context_validator is not None and any(not bool(context_validator(r)) for r in (*ad,*av)):continue\n        prepared_specs.append((spec,ad,av))\n        discovery_query_keys.update(context_key(schema,row) for row in ad)\n        validation_query_keys.update(context_key(schema,row) for row in av)\n    overlap=discovery_query_keys & validation_query_keys\n    if overlap:\n        raise ValueError('discovery and validation oracle-query universes must be semantically disjoint')\n\n    oracle_calls=0;queried=set()\n"""
if text.count(old_budget) != 1:
    raise SystemExit(f'budget anchor count != 1: {text.count(old_budget)}')
text = text.replace(old_budget, new_budget, 1)

old_profiles = """    specs=enumerate_interventions(schema.field_names,tuple(map(float,anchor_values)),arity=int(intervention_arity));profiles=[]\n    for spec in specs:\n        ad=tuple(spec.apply(r,schema.field_names) for r in discovery);av=tuple(spec.apply(r,schema.field_names) for r in validation)\n        if context_validator is not None and any(not bool(context_validator(r)) for r in (*ad,*av)):continue\n        dv=[];vv=[]\n"""
new_profiles = """    profiles=[]\n    for spec,ad,av in prepared_specs:\n        dv=[];vv=[]\n"""
if text.count(old_profiles) != 1:
    raise SystemExit(f'profiles anchor count != 1: {text.count(old_profiles)}')
text = text.replace(old_profiles, new_profiles, 1)

path.write_text(text)
print('R268_LEARNING_VALIDATION_QUERY_DISJOINTNESS_PATCH_APPLIED')
