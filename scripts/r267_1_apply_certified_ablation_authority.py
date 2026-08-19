from __future__ import annotations

from pathlib import Path


path = Path('cogcoder/r267_three_probe_causal_composition.py')
text = path.read_text()

marker = "def _examples_have_target_collision(examples: Sequence[OperatorExample]) -> bool:"
if marker not in text:
    raise SystemExit('apply the R2.67.1 genuine-necessity core patch first')

old = "if not result.passed and 'budget_exhausted' in result.reason:\n                candidate_ablation_inconclusive = True"
new = "if not result.passed:\n                candidate_ablation_inconclusive = True"
count = text.count(old)
if count != 2:
    raise SystemExit(f'expected two uncertified-ablation search-miss surfaces, found {count}')

text = text.replace(old, new)
path.write_text(text)
print('R267_1_CERTIFIED_ABLATION_AUTHORITY_PATCH_APPLIED', count)
