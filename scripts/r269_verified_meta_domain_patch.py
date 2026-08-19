from __future__ import annotations

from pathlib import Path

PATH = Path('cogcoder/r269_meta_learning_kernel.py')
text = PATH.read_text(encoding='utf-8')
old = '''        if portable.role_count != len(signature.role_names):
            out.append(MatchedPrior(portable, False, 0, 'role_cardinality_mismatch'))
            continue
        required = _binary_ops(portable.canonical_expression)
'''
new = '''        if portable.role_count != len(signature.role_names):
            out.append(MatchedPrior(portable, False, 0, 'role_cardinality_mismatch'))
            continue
        if portable.adapter_type == 'verified_meta_episode_v1':
            scope = frozenset(portable.claim_scope)
            numeric_claim = f'numeric_domain={signature.numeric_domain}'
            domain_ok = numeric_claim in scope
            if signature.numeric_domain == 'finite_integer':
                exact_domain_claim = 'finite_integer_values=' + ','.join(map(str, signature.finite_integer_values))
                domain_ok = domain_ok and exact_domain_claim in scope
            if not domain_ok:
                out.append(MatchedPrior(portable, False, 0, 'verified_meta_domain_mismatch'))
                continue
        required = _binary_ops(portable.canonical_expression)
'''
if text.count(old) != 1:
    raise SystemExit(f'expected one matcher domain boundary, found {text.count(old)}')
updated = text.replace(old, new)
compile(updated, str(PATH), 'exec')
PATH.write_text(updated, encoding='utf-8')
