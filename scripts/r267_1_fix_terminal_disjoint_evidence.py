from __future__ import annotations

from pathlib import Path


OLD = '(9.0, -2.0, 6.0)'
NEW = '(9.0, -8.0, 6.0)'
FILES = (
    Path('benchmarks/kfigg/r267_1_genuine_three_probe.py'),
    Path('research/r267_1_external_cyclic_dot_transfer.py'),
)

for path in FILES:
    text = path.read_text()
    count = text.count(OLD)
    if count != 1:
        raise SystemExit(f'{path}: expected exactly one terminal collision row, found {count}')
    text = text.replace(OLD, NEW, 1)
    path.write_text(text)

print('R267_1_TERMINAL_DISJOINT_EVIDENCE_FIX_APPLIED', len(FILES))
