from __future__ import annotations

from pathlib import Path


path = Path('cogcoder/r267_three_probe_causal_composition.py')
text = path.read_text()

old_state = """    passing: list[ThreeProbeCandidate] = []\n    exhausted = False\n\n    for triplet_index, triplet in enumerate(triplets):\n"""
new_state = """    passing: list[ThreeProbeCandidate] = []\n    exhausted = False\n    ablation_inconclusive = False\n\n    for triplet_index, triplet in enumerate(triplets):\n"""
if text.count(old_state) != 1:
    raise SystemExit('R2.67 triplet search state surface changed concurrently')
text = text.replace(old_state, new_state, 1)

old_singleton = """        singleton_passed: list[bool] = []\n        singleton_counts: list[int] = []\n        for probe_index in range(3):\n            examples = _composition_examples(\n                schema,\n                selection_contexts,\n                all_targets,\n                triplet,\n                shared_positions,\n                (probe_index,),\n            )\n            result = _synthesize_r267_expression(\n                ('__p0',) + tuple(schema.canonical_fields[index] for index in shared_positions),\n                tuple(composition_constants),\n                examples,\n                max_depth=int(composition_max_depth),\n                max_candidates=ablation_cap,\n                beam_width=int(composition_beam_width),\n            )\n            singleton_passed.append(result.passed)\n            singleton_counts.append(result.candidates_considered)\n            total_singleton += result.candidates_considered\n        if any(singleton_passed):\n            continue\n\n        pair_passed: list[bool] = []\n"""
new_singleton = """        singleton_passed: list[bool] = []\n        singleton_counts: list[int] = []\n        singleton_inconclusive = False\n        for probe_index in range(3):\n            examples = _composition_examples(\n                schema,\n                selection_contexts,\n                all_targets,\n                triplet,\n                shared_positions,\n                (probe_index,),\n            )\n            result = _synthesize_r267_expression(\n                ('__p0',) + tuple(schema.canonical_fields[index] for index in shared_positions),\n                tuple(composition_constants),\n                examples,\n                max_depth=int(composition_max_depth),\n                max_candidates=ablation_cap,\n                beam_width=int(composition_beam_width),\n            )\n            singleton_passed.append(result.passed)\n            singleton_counts.append(result.candidates_considered)\n            total_singleton += result.candidates_considered\n            if not result.passed and 'budget_exhausted' in result.reason:\n                singleton_inconclusive = True\n                ablation_inconclusive = True\n        if any(singleton_passed) or singleton_inconclusive:\n            continue\n\n        pair_passed: list[bool] = []\n"""
if text.count(old_singleton) != 1:
    raise SystemExit('R2.67 singleton ablation surface changed concurrently')
text = text.replace(old_singleton, new_singleton, 1)

old_pair = """        pair_passed: list[bool] = []\n        pair_counts: list[int] = []\n        for pair in ((0, 1), (0, 2), (1, 2)):\n            examples = _composition_examples(\n                schema,\n                selection_contexts,\n                all_targets,\n                triplet,\n                shared_positions,\n                pair,\n            )\n            result = _synthesize_r267_expression(\n                ('__p0', '__p1') + tuple(schema.canonical_fields[index] for index in shared_positions),\n                tuple(composition_constants),\n                examples,\n                max_depth=int(composition_max_depth),\n                max_candidates=ablation_cap,\n                beam_width=int(composition_beam_width),\n            )\n            pair_passed.append(result.passed)\n            pair_counts.append(result.candidates_considered)\n            total_pair += result.candidates_considered\n        if any(pair_passed):\n            continue\n\n        values = tuple(evaluate_expr(full.expression, row.context) for row in full_examples)\n"""
new_pair = """        pair_passed: list[bool] = []\n        pair_counts: list[int] = []\n        pair_inconclusive = False\n        for pair in ((0, 1), (0, 2), (1, 2)):\n            examples = _composition_examples(\n                schema,\n                selection_contexts,\n                all_targets,\n                triplet,\n                shared_positions,\n                pair,\n            )\n            result = _synthesize_r267_expression(\n                ('__p0', '__p1') + tuple(schema.canonical_fields[index] for index in shared_positions),\n                tuple(composition_constants),\n                examples,\n                max_depth=int(composition_max_depth),\n                max_candidates=ablation_cap,\n                beam_width=int(composition_beam_width),\n            )\n            pair_passed.append(result.passed)\n            pair_counts.append(result.candidates_considered)\n            total_pair += result.candidates_considered\n            if not result.passed and 'budget_exhausted' in result.reason:\n                pair_inconclusive = True\n                ablation_inconclusive = True\n        if any(pair_passed) or pair_inconclusive:\n            continue\n\n        values = tuple(evaluate_expr(full.expression, row.context) for row in full_examples)\n"""
if text.count(old_pair) != 1:
    raise SystemExit('R2.67 pair ablation surface changed concurrently')
text = text.replace(old_pair, new_pair, 1)

old_reason = """        reason='three_probe_composition_discovered' if selected is not None else (\n            'composition_budget_exhausted' if exhausted else 'no_three_probe_composition'\n        ),\n"""
new_reason = """        reason='three_probe_composition_discovered' if selected is not None else (\n            'composition_budget_exhausted' if exhausted else (\n                'ablation_budget_exhausted' if ablation_inconclusive else 'no_three_probe_composition'\n            )\n        ),\n"""
if text.count(old_reason) != 1:
    raise SystemExit('R2.67 terminal structure reason surface changed concurrently')
text = text.replace(old_reason, new_reason, 1)

path.write_text(text)
print('R267_ABLATION_EXHAUSTION_FAIL_CLOSED_PATCH_APPLIED')
