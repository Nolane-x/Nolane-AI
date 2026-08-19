from pathlib import Path

path=Path('cogcoder/r268_adaptive_causal_basis.py')
text=path.read_text()
old="""    discovery_keys = {_context_key(schema, row) for row in discovery}\n    validation_keys = {_context_key(schema, row) for row in validation}\n    specs = enumerate_interventions(\n"""
new="""    discovery_keys = {_context_key(schema, row) for row in discovery}\n    validation_query_keys = [_context_key(schema, row) for row in validation]\n    validation_keys = set(validation_query_keys)\n    specs = enumerate_interventions(\n"""
if text.count(old)!=1: raise SystemExit(f'validation-key anchor count != 1: {text.count(old)}')
text=text.replace(old,new,1)
old="""        discovery_keys.update(_context_key(schema, row) for row in discovery_queries)\n        validation_keys.update(_context_key(schema, row) for row in validation_queries)\n\n    overlap = discovery_keys & validation_keys\n"""
new="""        discovery_keys.update(_context_key(schema, row) for row in discovery_queries)\n        validation_spec_keys = [_context_key(schema, row) for row in validation_queries]\n        validation_query_keys.extend(validation_spec_keys)\n        validation_keys.update(validation_spec_keys)\n\n    if len(validation_query_keys) != len(validation_keys):\n        raise ValueError(\n            'validation oracle query inputs must be semantically unique '\n            f'(duplicate_count={len(validation_query_keys)-len(validation_keys)})'\n        )\n\n    overlap = discovery_keys & validation_keys\n"""
if text.count(old)!=1: raise SystemExit(f'validation-update anchor count != 1: {text.count(old)}')
path.write_text(text.replace(old,new,1))
print('R268_VALIDATION_QUERY_UNIQUENESS_PATCH_APPLIED')
