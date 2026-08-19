from __future__ import annotations

from pathlib import Path


path = Path('cogcoder/r267_three_probe_causal_composition.py')
text = path.read_text()

start = text.index('def _synthesize_r267_expression(')
end = text.index('\ndef _composition_examples(', start)
replacement = '''def _synthesize_r267_expression(\n    field_names: Sequence[str],\n    constants: Sequence[object],\n    examples: Sequence[OperatorExample],\n    *,\n    max_depth: int,\n    max_candidates: int,\n    beam_width: int,\n) -> _ExpressionSearchReceipt:\n    \"\"\"Search the finite R2.67 authority grammar and expose incompleteness.\n\n    Authority must never infer causal necessity from failure of a heuristic beam.\n    The accepted search is therefore the finite union of the exact three-probe\n    algebraic closure, the complete bilinear-pair closure, and the bounded R2.66\n    contextual-router grammar.  Any exhausted stage is explicitly inconclusive.\n    \"\"\"\n    del beam_width  # retained in the public contract; not authority-bearing.\n    max_candidates = int(max_candidates)\n    if max_candidates < 1:\n        raise ValueError('max_candidates must be positive')\n\n    considered = 0\n    evaluations = 0\n    semantics = 0\n    required_probes = {'__p0', '__p1', '__p2'}\n\n    if required_probes <= set(map(str, field_names)):\n        structural_budget = min(max_candidates, 10_000)\n        structural = _synthesize_required_three_probe_skeleton(\n            tuple(constants), tuple(examples), max_candidates=structural_budget,\n        )\n        considered += structural.candidates_considered\n        evaluations += structural.evaluations\n        semantics += structural.semantic_candidates\n        if structural.passed and structural.expression is not None:\n            return _ExpressionSearchReceipt(\n                True, structural.expression, considered, evaluations, semantics, structural.reason,\n            )\n        if 'budget_exhausted' in structural.reason:\n            return _ExpressionSearchReceipt(\n                False, None, considered, evaluations, semantics,\n                'r267_expression_budget_exhausted',\n            )\n\n    remaining = max_candidates - considered\n    if remaining < 1:\n        return _ExpressionSearchReceipt(\n            False, None, considered, evaluations, semantics,\n            'r267_expression_budget_exhausted',\n        )\n\n    if int(max_depth) >= 2:\n        bilinear_budget = min(remaining, 5_000)\n        bilinear = _synthesize_bilinear_pair_skeleton(\n            tuple(field_names), tuple(examples), max_candidates=bilinear_budget,\n        )\n        considered += bilinear.candidates_considered\n        evaluations += bilinear.evaluations\n        semantics += bilinear.semantic_candidates\n        if bilinear.passed and bilinear.expression is not None:\n            return _ExpressionSearchReceipt(\n                True, bilinear.expression, considered, evaluations, semantics, bilinear.reason,\n            )\n        if 'budget_exhausted' in bilinear.reason:\n            return _ExpressionSearchReceipt(\n                False, None, considered, evaluations, semantics,\n                'r267_expression_budget_exhausted',\n            )\n\n    remaining = max_candidates - considered\n    if remaining < 1:\n        return _ExpressionSearchReceipt(\n            False, None, considered, evaluations, semantics,\n            'r267_expression_budget_exhausted',\n        )\n\n    router = synthesize_contextual_expression(\n        tuple(field_names),\n        tuple(constants),\n        tuple(examples),\n        max_depth=int(max_depth),\n        max_candidates=remaining,\n    )\n    considered += router.candidates_considered\n    evaluations += router.search_evaluations\n    semantics += router.semantic_candidates\n    if router.passed and router.expression is not None:\n        return _ExpressionSearchReceipt(\n            True, router.expression, considered, evaluations, semantics,\n            'r266_contextual_exact',\n        )\n    if router.reason == 'contextual_budget_exhausted':\n        return _ExpressionSearchReceipt(\n            False, None, considered, evaluations, semantics,\n            'r267_expression_budget_exhausted',\n        )\n    return _ExpressionSearchReceipt(\n        False, None, considered, evaluations, semantics,\n        'r267_complete_grammar_no_expression',\n    )\n\n'''
text = text[:start] + replacement + text[end + 1:]

old = '''    passing: list[ThreeProbeCandidate] = []\n    exhausted = False\n\n    for triplet_index, triplet in enumerate(triplets):\n'''
new = '''    passing: list[ThreeProbeCandidate] = []\n    exhausted = False\n    ablation_inconclusive = False\n\n    for triplet_index, triplet in enumerate(triplets):\n'''
if old not in text:
    raise SystemExit('R2.67 triplet state surface changed concurrently')
text = text.replace(old, new, 1)

old = '''        if not full.passed or full.expression is None:\n            if total_composition >= max_total:\n                exhausted = True\n            continue\n'''
new = '''        if not full.passed or full.expression is None:\n            if 'budget_exhausted' in full.reason or total_composition >= max_total:\n                exhausted = True\n            continue\n'''
if old not in text:
    raise SystemExit('R2.67 full-search failure surface changed concurrently')
text = text.replace(old, new, 1)

old = '''        singleton_passed: list[bool] = []\n        singleton_counts: list[int] = []\n        for probe_index in range(3):\n'''
new = '''        singleton_passed: list[bool] = []\n        singleton_counts: list[int] = []\n        candidate_ablation_inconclusive = False\n        for probe_index in range(3):\n'''
if old not in text:
    raise SystemExit('R2.67 singleton state surface changed concurrently')
text = text.replace(old, new, 1)

old = '''            singleton_passed.append(result.passed)\n            singleton_counts.append(result.candidates_considered)\n            total_singleton += result.candidates_considered\n        if any(singleton_passed):\n            continue\n\n        pair_passed: list[bool] = []\n'''
new = '''            singleton_passed.append(result.passed)\n            singleton_counts.append(result.candidates_considered)\n            total_singleton += result.candidates_considered\n            if not result.passed and 'budget_exhausted' in result.reason:\n                candidate_ablation_inconclusive = True\n        if any(singleton_passed):\n            continue\n        if candidate_ablation_inconclusive:\n            ablation_inconclusive = True\n            continue\n\n        pair_passed: list[bool] = []\n'''
if old not in text:
    raise SystemExit('R2.67 singleton conclusion surface changed concurrently')
text = text.replace(old, new, 1)

old = '''            pair_passed.append(result.passed)\n            pair_counts.append(result.candidates_considered)\n            total_pair += result.candidates_considered\n        if any(pair_passed):\n            continue\n\n        values = tuple(evaluate_expr(full.expression, row.context) for row in full_examples)\n'''
new = '''            pair_passed.append(result.passed)\n            pair_counts.append(result.candidates_considered)\n            total_pair += result.candidates_considered\n            if not result.passed and 'budget_exhausted' in result.reason:\n                candidate_ablation_inconclusive = True\n        if any(pair_passed):\n            continue\n        if candidate_ablation_inconclusive:\n            ablation_inconclusive = True\n            continue\n\n        values = tuple(evaluate_expr(full.expression, row.context) for row in full_examples)\n'''
if old not in text:
    raise SystemExit('R2.67 pair conclusion surface changed concurrently')
text = text.replace(old, new, 1)

old = '''        reason='three_probe_composition_discovered' if selected is not None else (\n            'composition_budget_exhausted' if exhausted else 'no_three_probe_composition'\n        ),\n'''
new = '''        reason='three_probe_composition_discovered' if selected is not None else (\n            'ablation_search_inconclusive' if ablation_inconclusive else (\n                'composition_budget_exhausted' if exhausted else 'no_three_probe_composition'\n            )\n        ),\n'''
if old not in text:
    raise SystemExit('R2.67 final reason surface changed concurrently')
text = text.replace(old, new, 1)

path.write_text(text)
print('R267_COMPLETE_ABLATION_AUTHORITY_PATCH_APPLIED')
