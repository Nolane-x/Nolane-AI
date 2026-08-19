from __future__ import annotations

from pathlib import Path


path = Path('cogcoder/r267_three_probe_causal_composition.py')
text = path.read_text()

# 1) Add a bounded constructive closure that can expose the exact lower-order
# residual used by the old tri-bilinear benchmark once genuine pair-specific
# free fields are restored.
marker = '''def _synthesize_r267_expression(
'''
if marker not in text:
    raise SystemExit('R2.67 expression search surface changed concurrently')
helper = '''def _synthesize_probe_pair_product_residual(
    field_names: Sequence[str],
    examples: Sequence[OperatorExample],
    *,
    max_candidates: int,
) -> _ExpressionSearchReceipt:
    """Enumerate two-probe +/- one-original-product residual identities.

    This closure is deliberately field-agnostic and finite.  It exists so a
    lower-order causal claim cannot survive merely because the generic router
    fails to enumerate identities such as ``p0 + p1 - x*y`` early enough.
    """
    fields = tuple(sorted({str(value).strip() for value in field_names if str(value).strip()}))
    if '__p0' not in fields or '__p1' not in fields or '__p2' in fields:
        return _ExpressionSearchReceipt(False, None, 0, 0, 0, 'probe_pair_residual_not_applicable')
    originals = tuple(field for field in fields if not field.startswith('__p'))
    if len(originals) < 1:
        return _ExpressionSearchReceipt(False, None, 0, 0, 0, 'probe_pair_residual_no_original_fields')
    rows = tuple(examples)
    target = tuple(_finite_json_value(row.expected) for row in rows)
    limit = int(max_candidates)
    if limit < 1:
        raise ValueError('max_candidates must be positive')
    considered = 0
    evaluations = 0
    semantic_seen: set[str] = set()
    digests: set[str] = set()
    p0 = Field('__p0')
    p1 = Field('__p1')
    probe_bases = (
        Binary('add', p0, p1),
        Binary('sub', p0, p1),
        Binary('sub', p1, p0),
    )
    product_terms = tuple(
        Binary('mul', Field(left), Field(right))
        for left, right in itertools.combinations_with_replacement(originals, 2)
    )

    for base in probe_bases:
        for product in product_terms:
            for expression in (
                Binary('add', base, product),
                Binary('sub', base, product),
                Binary('sub', product, base),
            ):
                if considered >= limit:
                    return _ExpressionSearchReceipt(
                        False, None, considered, evaluations, len(semantic_seen),
                        'probe_pair_residual_budget_exhausted',
                    )
                digest = expr_digest(expression)
                if digest in digests:
                    continue
                digests.add(digest)
                considered += 1
                values, count = _evaluate_vector(expression, rows)
                evaluations += count
                if values is None:
                    continue
                semantic_seen.add(semantic_vector_key(values))
                if all(_equivalent(actual, expected) for actual, expected in zip(values, target, strict=True)):
                    return _ExpressionSearchReceipt(
                        True, expression, considered, evaluations, len(semantic_seen),
                        'probe_pair_residual_exact',
                    )
    return _ExpressionSearchReceipt(
        False, None, considered, evaluations, len(semantic_seen),
        'probe_pair_residual_no_exact_expression',
    )


def _examples_have_target_collision(examples: Sequence[OperatorExample]) -> bool:
    """Return true when identical public evidence maps to distinct targets.

    Such a collision is an information-theoretic certificate that no
    deterministic expression over the exposed lower-order evidence can solve
    the examples; no exhaustive DSL search is required to falsify that subset.
    """
    seen: dict[str, object] = {}
    for row in examples:
        fields = tuple(sorted(row.context))
        key = semantic_vector_key(tuple(row.context[field] for field in fields))
        expected = _finite_json_value(row.expected)
        if key in seen and not _equivalent(seen[key], expected):
            return True
        seen[key] = expected
    return False


'''
text = text.replace(marker, helper + marker, 1)

# 2) Add the two-probe residual closure before generic bilinear/router search.
old = '''    if int(max_depth) >= 2:
        bilinear_budget = min(remaining, 5_000)
'''
new = '''    available_fields = set(map(str, field_names))
    if {'__p0', '__p1'} <= available_fields and '__p2' not in available_fields:
        residual_budget = min(remaining, 5_000)
        residual = _synthesize_probe_pair_product_residual(
            tuple(field_names), tuple(examples), max_candidates=residual_budget,
        )
        considered += residual.candidates_considered
        evaluations += residual.evaluations
        semantics += residual.semantic_candidates
        if residual.passed and residual.expression is not None:
            return _ExpressionSearchReceipt(
                True, residual.expression, considered, evaluations, semantics, residual.reason,
            )
        if 'budget_exhausted' in residual.reason:
            return _ExpressionSearchReceipt(
                False, None, considered, evaluations, semantics,
                'r267_expression_budget_exhausted',
            )
        remaining = max_candidates - considered
        if remaining < 1:
            return _ExpressionSearchReceipt(
                False, None, considered, evaluations, semantics,
                'r267_expression_budget_exhausted',
            )

    if int(max_depth) >= 2:
        bilinear_budget = min(remaining, 5_000)
'''
if old not in text:
    raise SystemExit('R2.67 bilinear search insertion surface changed concurrently')
text = text.replace(old, new, 1)

# 3) Lower-order singleton evidence regains every original position not
# overwritten by that singleton itself.  Collisions are conclusive failures.
old = '''        for probe_index in range(3):
            examples = _composition_examples(
                schema,
                selection_contexts,
                all_targets,
                triplet,
                shared_positions,
                (probe_index,),
            )
            result = _synthesize_r267_expression(
                ('__p0',) + tuple(schema.canonical_fields[index] for index in shared_positions),
                tuple(composition_constants),
                examples,
                max_depth=int(composition_max_depth),
                max_candidates=ablation_cap,
                beam_width=int(composition_beam_width),
            )
            singleton_passed.append(result.passed)
            singleton_counts.append(result.candidates_considered)
            total_singleton += result.candidates_considered
            if not result.passed and 'budget_exhausted' in result.reason:
                candidate_ablation_inconclusive = True
'''
new = '''        for probe_index in range(3):
            subset = (probe_index,)
            subset_fixed_positions = {
                position
                for profile_index in subset
                for position, _value in triplet[profile_index].intervention.bindings
            }
            subset_shared_positions = tuple(
                index for index in range(len(schema.field_names))
                if index not in subset_fixed_positions
            )
            examples = _composition_examples(
                schema,
                selection_contexts,
                all_targets,
                triplet,
                subset_shared_positions,
                subset,
            )
            if _examples_have_target_collision(examples):
                singleton_passed.append(False)
                singleton_counts.append(0)
                continue
            result = _synthesize_r267_expression(
                ('__p0',) + tuple(schema.canonical_fields[index] for index in subset_shared_positions),
                tuple(composition_constants),
                examples,
                max_depth=int(composition_max_depth),
                max_candidates=ablation_cap,
                beam_width=int(composition_beam_width),
            )
            singleton_passed.append(result.passed)
            singleton_counts.append(result.candidates_considered)
            total_singleton += result.candidates_considered
            if not result.passed and 'budget_exhausted' in result.reason:
                candidate_ablation_inconclusive = True
'''
if old not in text:
    raise SystemExit('R2.67 singleton ablation surface changed concurrently')
text = text.replace(old, new, 1)

# 4) Same correction for every pair subset.
old = '''        for pair in ((0, 1), (0, 2), (1, 2)):
            examples = _composition_examples(
                schema,
                selection_contexts,
                all_targets,
                triplet,
                shared_positions,
                pair,
            )
            result = _synthesize_r267_expression(
                ('__p0', '__p1') + tuple(schema.canonical_fields[index] for index in shared_positions),
                tuple(composition_constants),
                examples,
                max_depth=int(composition_max_depth),
                max_candidates=ablation_cap,
                beam_width=int(composition_beam_width),
            )
            pair_passed.append(result.passed)
            pair_counts.append(result.candidates_considered)
            total_pair += result.candidates_considered
            if not result.passed and 'budget_exhausted' in result.reason:
                candidate_ablation_inconclusive = True
'''
new = '''        for pair in ((0, 1), (0, 2), (1, 2)):
            subset_fixed_positions = {
                position
                for profile_index in pair
                for position, _value in triplet[profile_index].intervention.bindings
            }
            subset_shared_positions = tuple(
                index for index in range(len(schema.field_names))
                if index not in subset_fixed_positions
            )
            examples = _composition_examples(
                schema,
                selection_contexts,
                all_targets,
                triplet,
                subset_shared_positions,
                pair,
            )
            if _examples_have_target_collision(examples):
                pair_passed.append(False)
                pair_counts.append(0)
                continue
            result = _synthesize_r267_expression(
                ('__p0', '__p1') + tuple(schema.canonical_fields[index] for index in subset_shared_positions),
                tuple(composition_constants),
                examples,
                max_depth=int(composition_max_depth),
                max_candidates=ablation_cap,
                beam_width=int(composition_beam_width),
            )
            pair_passed.append(result.passed)
            pair_counts.append(result.candidates_considered)
            total_pair += result.candidates_considered
            if not result.passed and 'budget_exhausted' in result.reason:
                candidate_ablation_inconclusive = True
'''
if old not in text:
    raise SystemExit('R2.67 pair ablation surface changed concurrently')
text = text.replace(old, new, 1)

# 5) Correct public receipt units after a three-probe program has been selected.
old = '''    selected = structure.selected
    probe_canonical: list[Expr] = []
'''
new = '''    selected = structure.selected
    planned_probe_validation_cases = len(validation) * len(selected.profiles)
    probe_canonical: list[Expr] = []
'''
if old not in text:
    raise SystemExit('R2.67 selected receipt surface changed concurrently')
text = text.replace(old, new, 1)
selected_index = text.index('    selected = structure.selected\n')
prefix = text[:selected_index]
suffix = text[selected_index:]
count = suffix.count('probe_validation_cases=len(validation),')
if count < 1:
    raise SystemExit('R2.67 probe-validation receipt units surface changed concurrently')
suffix = suffix.replace(
    'probe_validation_cases=len(validation),',
    'probe_validation_cases=planned_probe_validation_cases,',
)
text = prefix + suffix

path.write_text(text)
print('R267_1_GENUINE_CAUSAL_NECESSITY_CORE_PATCH_APPLIED', count)
