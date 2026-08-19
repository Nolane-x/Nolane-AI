from __future__ import annotations

from pathlib import Path


SOURCE = Path('cogcoder/r268_cross_task_causal_transfer.py')

OLD_RAW = '''    try:
        raw = oracle(oracle_context)
    except (ArithmeticError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        after_token = _oracle_context_token(oracle_context)
        if oracle_context.mutation_attempted or after_token != before_token:
            return 'mutation', None, semantic_context
        return 'invalid', None, semantic_context
'''
NEW_RAW = '''    try:
        raw = oracle(oracle_context)
    except Exception:
        # Ordinary external-oracle failures are evidence failures, not solver
        # process failures. Deliberately do not catch BaseException subclasses
        # such as KeyboardInterrupt or SystemExit.
        after_token = _oracle_context_token(oracle_context)
        if oracle_context.mutation_attempted or after_token != before_token:
            return 'mutation', None, semantic_context
        return 'invalid', None, semantic_context
'''

OLD_OUTPUT = '''    try:
        observed = _canonical_number(raw)
    except (ArithmeticError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return 'invalid', None, semantic_context
'''
NEW_OUTPUT = '''    try:
        observed = _canonical_number(raw)
    except Exception:
        return 'invalid', None, semantic_context
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one replacement boundary, found {count}')
    return text.replace(old, new, 1)


def main() -> None:
    text = SOURCE.read_text(encoding='utf-8')
    if 'except Exception:' in text and 'Ordinary external-oracle failures' in text:
        print('R268T_ORACLE_EXCEPTION_CONTAINMENT_ALREADY_MATERIALIZED')
        return
    text = replace_once(text, OLD_RAW, NEW_RAW, 'oracle call exception boundary')
    text = replace_once(text, OLD_OUTPUT, NEW_OUTPUT, 'oracle output exception boundary')
    compile(text, str(SOURCE), 'exec')
    SOURCE.write_text(text, encoding='utf-8')
    print('R268T_ORACLE_EXCEPTION_CONTAINMENT_MATERIALIZED')


if __name__ == '__main__':
    main()
