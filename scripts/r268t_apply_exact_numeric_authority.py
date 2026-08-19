from __future__ import annotations

from pathlib import Path


SOURCE = Path('cogcoder/r268_cross_task_causal_transfer.py')

OLD = '''def _equivalent(left: object, right: object) -> bool:
    try:
        a = _finite_number(left)
        b = _finite_number(right)
    except (TypeError, ValueError):
        return False
    if isinstance(a, float) or isinstance(b, float):
        return math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-10)
    return a == b
'''

NEW = '''def _equivalent(left: object, right: object) -> bool:
    try:
        a = _canonical_number(left)
        b = _canonical_number(right)
    except (TypeError, ValueError):
        return False
    # R2.68-T receipts claim exact numeric agreement. Integral floats are
    # normalized to integers by _canonical_number; non-integral finite floats
    # retain their actual runtime value. Magnitude-dependent tolerance is not
    # authority for candidate selection or terminal acceptance.
    return a == b
'''


def main() -> None:
    text = SOURCE.read_text(encoding='utf-8')
    if 'Magnitude-dependent tolerance is not' in text:
        print('R268T_EXACT_NUMERIC_AUTHORITY_ALREADY_MATERIALIZED')
        return
    count = text.count(OLD)
    if count != 1:
        raise SystemExit(f'expected exactly one numeric-equivalence boundary, found {count}')
    text = text.replace(OLD, NEW, 1)
    compile(text, str(SOURCE), 'exec')
    SOURCE.write_text(text, encoding='utf-8')
    print('R268T_EXACT_NUMERIC_AUTHORITY_MATERIALIZED')


if __name__ == '__main__':
    main()
