from __future__ import annotations

from pathlib import Path


TRANSFER = Path('cogcoder/r268_cross_task_causal_transfer.py')
SCRATCH = Path('cogcoder/r268_cross_task_transfer_baseline.py')

HELPER_ANCHOR = '''def _context_key(context: Mapping[str, object]) -> str:
    return json.dumps(_context_values(context), separators=(',', ':'), allow_nan=False)


'''
HELPER = '''def _snapshot_context_groups(
    *groups: Sequence[Mapping[str, object]],
) -> tuple[tuple[dict[str, int | float], ...], ...]:
    # Freeze each caller-owned Mapping object exactly once. Identity caching is
    # required because the same stateful Mapping may appear in more than one
    # authority collection; one object cannot masquerade as multiple semantic
    # rows by changing values between reads.
    cache: dict[int, tuple[Mapping[str, object], dict[str, int | float]]] = {}

    def snapshot(context: Mapping[str, object]) -> dict[str, int | float]:
        identity = id(context)
        cached = cache.get(identity)
        if cached is not None and cached[0] is context:
            return cached[1]
        values = _context_values(context)
        frozen = dict(zip(_PROBE_ROLES, values, strict=True))
        cache[identity] = (context, frozen)
        return frozen

    return tuple(tuple(snapshot(row) for row in group) for group in groups)


'''

TRANSFER_OLD = '''    diagnostics = tuple(diagnostic_contexts)
    terminals = tuple(terminal_contexts)
    if not diagnostics:
'''
TRANSFER_NEW = '''    diagnostics, terminals = _snapshot_context_groups(
        diagnostic_contexts,
        terminal_contexts,
    )
    if not diagnostics:
'''

SCRATCH_IMPORT_OLD = '''    _proven_structural_alias_key,
    _safe_prediction,
)
'''
SCRATCH_IMPORT_NEW = '''    _proven_structural_alias_key,
    _safe_prediction,
    _snapshot_context_groups,
)
'''

SCRATCH_OLD = '''    diagnostics = tuple(diagnostic_contexts)
    terminals = tuple(terminal_contexts)
    if not diagnostics:
'''
SCRATCH_NEW = '''    diagnostics, terminals = _snapshot_context_groups(
        diagnostic_contexts,
        terminal_contexts,
    )
    if not diagnostics:
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
        'def _snapshot_context_groups(' in transfer
        and '_snapshot_context_groups,' in scratch
        and 'diagnostics, terminals = _snapshot_context_groups(' in transfer
        and 'diagnostics, terminals = _snapshot_context_groups(' in scratch
    )
    if already:
        print('R268T_INPUT_CONTEXT_SNAPSHOT_ALREADY_MATERIALIZED')
        return

    transfer = replace_once(transfer, HELPER_ANCHOR, HELPER_ANCHOR + HELPER, 'snapshot helper')
    transfer = replace_once(transfer, TRANSFER_OLD, TRANSFER_NEW, 'transfer ingress')
    scratch = replace_once(scratch, SCRATCH_IMPORT_OLD, SCRATCH_IMPORT_NEW, 'scratch snapshot import')
    scratch = replace_once(scratch, SCRATCH_OLD, SCRATCH_NEW, 'scratch ingress')

    compile(transfer, str(TRANSFER), 'exec')
    compile(scratch, str(SCRATCH), 'exec')
    TRANSFER.write_text(transfer, encoding='utf-8')
    SCRATCH.write_text(scratch, encoding='utf-8')
    print('R268T_INPUT_CONTEXT_SNAPSHOT_MATERIALIZED')


if __name__ == '__main__':
    main()
