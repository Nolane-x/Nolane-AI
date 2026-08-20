from __future__ import annotations

from pathlib import Path


def patch_adapter() -> None:
    path = Path('cogcoder/r269_causal_basis_adapter.py')
    text = path.read_text(encoding='utf-8')
    marker = "_CLAIM_SCOPE = ('r268_verified_adaptive_basis', 'globally_minimal', 'proof_ledger_complete')\n"
    addition = marker + "_ALLOWED_ADAPTER_TYPES = frozenset(('causal_basis_v1', 'verified_meta_episode_v1'))\n"
    if '_ALLOWED_ADAPTER_TYPES' not in text:
        if text.count(marker) != 1:
            raise SystemExit('unexpected R2.69 adapter constant boundary')
        text = text.replace(marker, addition, 1)
    old = "        if self.adapter_type != 'causal_basis_v1':\n            raise ValueError('unsupported adapter_type')\n"
    new = "        if self.adapter_type not in _ALLOWED_ADAPTER_TYPES:\n            raise ValueError('unsupported adapter_type')\n"
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise SystemExit('unexpected PortableExperience adapter boundary')
    compile(text, str(path), 'exec')
    path.write_text(text, encoding='utf-8')


def patch_matcher() -> None:
    path = Path('cogcoder/r269_meta_learning_kernel.py')
    text = path.read_text(encoding='utf-8')
    old = """        if portable.role_count != len(signature.role_names):
            out.append(MatchedPrior(portable, False, 0, 'role_cardinality_mismatch'))
            continue
        required = _binary_ops(portable.canonical_expression)
"""
    new = """        if portable.role_count != len(signature.role_names):
            out.append(MatchedPrior(portable, False, 0, 'role_cardinality_mismatch'))
            continue
        if portable.adapter_type == 'verified_meta_episode_v1':
            scope = frozenset(portable.claim_scope)
            domain_ok = f'numeric_domain={signature.numeric_domain}' in scope
            if signature.numeric_domain == 'finite_integer':
                exact_domain = 'finite_integer_values=' + ','.join(map(str, signature.finite_integer_values))
                domain_ok = domain_ok and exact_domain in scope
            if not domain_ok:
                out.append(MatchedPrior(portable, False, 0, 'verified_meta_domain_mismatch'))
                continue
        required = _binary_ops(portable.canonical_expression)
"""
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise SystemExit('unexpected R2.69 matcher boundary')
    compile(text, str(path), 'exec')
    path.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    patch_adapter()
    patch_matcher()
    print('R269_SEQUENTIAL_META_INTEGRATION_PATCHED')
