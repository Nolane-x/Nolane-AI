from __future__ import annotations

from pathlib import Path


FILES = (
    Path('cogcoder/r268_cross_task_causal_transfer.py'),
    Path('cogcoder/r268_cross_task_transfer_baseline.py'),
)

OLD = """    live_after_selection = len(live)\n    terminal_queries = 0\n"""
NEW = """    live_after_selection = len(live)\n    if live_after_selection != 1:\n        return _failed_receipt(\n            candidates_generated=len(generated),\n            live=live,\n            selection_queries=selection_queries,\n            terminal_queries=0,\n            terminal_exact=0,\n            reason='ambiguous_after_selection',\n            trace=trace,\n        )\n\n    terminal_queries = 0\n"""


def main() -> None:
    changed = 0
    for path in FILES:
        text = path.read_text(encoding='utf-8')
        if NEW in text:
            continue
        count = text.count(OLD)
        if count != 1:
            raise SystemExit(f'{path}: expected exactly one guarded insertion point, found {count}')
        path.write_text(text.replace(OLD, NEW, 1), encoding='utf-8')
        changed += 1
    print(f'R268T_TERMINAL_VERIFICATION_ONLY_CHANGED={changed}')


if __name__ == '__main__':
    main()
