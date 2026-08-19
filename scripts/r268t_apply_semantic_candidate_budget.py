from __future__ import annotations

from pathlib import Path


TRANSFER = Path('cogcoder/r268_cross_task_causal_transfer.py')
SCRATCH = Path('cogcoder/r268_cross_task_transfer_baseline.py')

TRANSFER_OLD = '''    generated = generate_transfer_candidates(portable)[:max_candidates]
    live = _dedupe_live_candidates(generated, diagnostics)
'''
TRANSFER_NEW = '''    # max_candidates is a semantic-hypothesis budget. Proof-equivalent AST
    # representations cannot consume multiple slots before selection.
    generated = tuple(
        _dedupe_live_candidates(generate_transfer_candidates(portable), diagnostics)[:max_candidates]
    )
    live = list(generated)
'''

SCRATCH_IMPORT_OLD = '''    _failed_receipt,
    _safe_prediction,
)
'''
SCRATCH_IMPORT_NEW = '''    _failed_receipt,
    _proven_structural_alias_key,
    _safe_prediction,
)
'''

SCRATCH_SEEN_OLD = '''    out: list[TransferCandidate] = []
    seen: set[str] = set()

    def add(expr: Expr) -> bool:
        if len(out) >= max_candidates:
            return False
        from .r256_operator_dsl import expr_digest

        digest = expr_digest(expr)
        if digest in seen:
            return True
        seen.add(digest)
        ordinal = len(out)
'''
SCRATCH_SEEN_NEW = '''    out: list[TransferCandidate] = []
    seen_semantic_hypotheses: set[str] = set()

    def add(expr: Expr) -> bool:
        if len(out) >= max_candidates:
            return False
        from .r256_operator_dsl import expr_digest

        semantic_key = _proven_structural_alias_key(expr)
        if semantic_key in seen_semantic_hypotheses:
            return True
        seen_semantic_hypotheses.add(semantic_key)
        digest = expr_digest(expr)
        ordinal = len(out)
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one replacement boundary, found {count}')
    return text.replace(old, new, 1)


def main() -> None:
    transfer = TRANSFER.read_text(encoding='utf-8')
    scratch = SCRATCH.read_text(encoding='utf-8')

    already = (
        'generated = tuple(\n        _dedupe_live_candidates(generate_transfer_candidates(portable), diagnostics)[:max_candidates]' in transfer
        and 'seen_semantic_hypotheses' in scratch
        and '_proven_structural_alias_key,' in scratch
    )
    if already:
        print('R268T_SEMANTIC_CANDIDATE_BUDGET_ALREADY_MATERIALIZED')
        return

    transfer = replace_once(transfer, TRANSFER_OLD, TRANSFER_NEW, 'transfer candidate budget')
    scratch = replace_once(scratch, SCRATCH_IMPORT_OLD, SCRATCH_IMPORT_NEW, 'scratch semantic-key import')
    scratch = replace_once(scratch, SCRATCH_SEEN_OLD, SCRATCH_SEEN_NEW, 'scratch candidate budget')

    compile(transfer, str(TRANSFER), 'exec')
    compile(scratch, str(SCRATCH), 'exec')
    TRANSFER.write_text(transfer, encoding='utf-8')
    SCRATCH.write_text(scratch, encoding='utf-8')
    print('R268T_SEMANTIC_CANDIDATE_BUDGET_MATERIALIZED')


if __name__ == '__main__':
    main()
