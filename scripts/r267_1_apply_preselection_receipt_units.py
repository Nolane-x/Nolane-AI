from __future__ import annotations

from pathlib import Path

path = Path('cogcoder/r267_three_probe_causal_composition.py')
text = path.read_text()
old = """            probe_expressions=(),
            probe_candidates_considered=(),
            probe_validation_cases=len(validation),
            probe_validation_exact=0,
            final_validation_cases=len(terminal),
            final_validation_exact=0,
            reason='structure_discovery_failed',
"""
new = """            probe_expressions=(),
            probe_candidates_considered=(),
            probe_validation_cases=0,
            probe_validation_exact=0,
            final_validation_cases=len(terminal),
            final_validation_exact=0,
            reason='structure_discovery_failed',
"""
count = text.count(old)
if count != 1:
    raise SystemExit(f'expected one preselection receipt surface, found {count}')
text = text.replace(old, new, 1)
path.write_text(text)
print('R267_1_PRESELECTION_RECEIPT_UNITS_PATCH_APPLIED')
