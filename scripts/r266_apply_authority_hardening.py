from __future__ import annotations

from pathlib import Path


def patch_core() -> None:
    path = Path('cogcoder/_r266_contextual_composition_core.py')
    text = path.read_text()
    old_profile = """def _profile_semantic_id(profile: ContextualInterventionProfile) -> str:\n    raw = json.dumps(list(profile.outputs), sort_keys=True, separators=(',', ':'), allow_nan=False)\n    return hashlib.sha256(raw.encode('utf-8')).hexdigest()\n"""
    new_profile = """def _profile_semantic_id(profile: ContextualInterventionProfile) -> str:\n    raw = semantic_vector_key(profile.outputs)\n    return hashlib.sha256(raw.encode('utf-8')).hexdigest()\n"""
    if old_profile in text:
        assert text.count(old_profile) == 1
        text = text.replace(old_profile, new_profile, 1)
    elif new_profile not in text:
        raise SystemExit('R2.66 semantic-profile surface changed concurrently')

    old_receipt = """    reason: str\n    trainable_parameter_count: int = 0\n\n\ndef synthesize_contextual_composition_program(\n"""
    new_receipt = """    reason: str\n    trainable_parameter_count: int = 0\n    oracle_calls_total: int = 0\n    terminal_probe_validation_cases: int = 0\n    terminal_probe_validation_exact: int = 0\n\n\ndef synthesize_contextual_composition_program(\n"""
    if old_receipt in text:
        assert text.count(old_receipt) == 1
        text = text.replace(old_receipt, new_receipt, 1)
    elif 'terminal_probe_validation_exact: int = 0' not in text:
        raise SystemExit('R2.66 synthesis receipt surface changed concurrently')
    path.write_text(text)


def patch_public() -> None:
    path = Path('cogcoder/r266_learned_contextual_composition.py')
    text = path.read_text()
    old_import = 'import json\nfrom typing import Callable, Mapping, Sequence\n'
    new_import = 'from dataclasses import replace\nfrom typing import Callable, Mapping, Sequence\n'
    if old_import in text:
        text = text.replace(old_import, new_import, 1)
    elif 'from dataclasses import replace' not in text:
        raise SystemExit('R2.66 public import surface changed concurrently')

    anchor = 'from .r258_intervention_discovery import PositionalSchema\n'
    if 'from .r259_semantic_index_core import semantic_vector_key\n' not in text:
        assert text.count(anchor) == 1
        text = text.replace(anchor, anchor + 'from .r259_semantic_index_core import semantic_vector_key\n', 1)

    old_key = """def _context_key(schema: PositionalSchema, context: Mapping[str, object]) -> tuple[tuple[str, str], ...]:\n    canonical = schema.to_canonical_context(context)\n    rows: list[tuple[str, str]] = []\n    for field in schema.canonical_fields:\n        encoded = json.dumps(\n            canonical[field],\n            sort_keys=True,\n            separators=(',', ':'),\n            allow_nan=False,\n        )\n        rows.append((field, encoded))\n    return tuple(rows)\n"""
    new_key = """def _context_key(schema: PositionalSchema, context: Mapping[str, object]) -> str:\n    canonical = schema.to_canonical_context(context)\n    return semantic_vector_key(tuple(canonical[field] for field in schema.canonical_fields))\n"""
    if old_key in text:
        assert text.count(old_key) == 1
        text = text.replace(old_key, new_key, 1)
    elif new_key not in text:
        raise SystemExit('R2.66 context-key surface changed concurrently')
    text = text.replace('learning_keys: set[tuple[tuple[str, str], ...]] = set()', 'learning_keys: set[str] = set()', 1)
    text = text.replace('terminal_keys: set[tuple[tuple[str, str], ...]] = set()', 'terminal_keys: set[str] = set()', 1)

    marker = """    internal = _core_synthesize_contextual_composition_program(\n        oracle,\n"""
    ledger = """    oracle_calls_total = 0\n    queried_keys: set[str] = set()\n\n    def tracked_oracle(context: Mapping[str, object]) -> object:\n        nonlocal oracle_calls_total\n        queried_keys.add(_context_key(schema, context))\n        oracle_calls_total += 1\n        return oracle(dict(context))\n\n    internal = _core_synthesize_contextual_composition_program(\n        tracked_oracle,\n"""
    if marker in text:
        assert text.count(marker) == 1
        text = text.replace(marker, ledger, 1)
    elif 'def tracked_oracle' not in text:
        raise SystemExit('R2.66 oracle-ledger insertion surface changed concurrently')

    old_tail = """    if not internal.passed or internal.expression is None:\n        return internal\n\n    exact = 0\n    try:\n        for context in terminal:\n            expected = oracle(dict(context))\n            actual = evaluate_expr(internal.expression, context)\n            exact += int(_equivalent(actual, expected))\n    except Exception:\n        return ContextualCompositionSynthesisReceipt(\n            False,\n            internal.structure,\n            internal.expression,\n            internal.probe_expressions,\n            internal.probe_candidates_considered,\n            internal.probe_validation_cases,\n            internal.probe_validation_exact,\n            len(terminal),\n            exact,\n            'independent_terminal_verification_error',\n            0,\n        )\n\n    if exact != len(terminal):\n        return ContextualCompositionSynthesisReceipt(\n            False,\n            internal.structure,\n            internal.expression,\n            internal.probe_expressions,\n            internal.probe_candidates_considered,\n            internal.probe_validation_cases,\n            internal.probe_validation_exact,\n            len(terminal),\n            exact,\n            'independent_terminal_verification_failed',\n            0,\n        )\n\n    return ContextualCompositionSynthesisReceipt(\n        True,\n        internal.structure,\n        internal.expression,\n        internal.probe_expressions,\n        internal.probe_candidates_considered,\n        internal.probe_validation_cases,\n        internal.probe_validation_exact,\n        len(terminal),\n        exact,\n        'contextual_program_synthesized_terminally_verified',\n        0,\n    )\n"""
    new_tail = """    learning_query_keys = frozenset(queried_keys)\n    if terminal_keys & learning_query_keys:\n        raise ValueError('terminal_contexts must be disjoint from all oracle query inputs used for learning')\n    if not internal.passed or internal.expression is None:\n        return replace(internal, oracle_calls_total=oracle_calls_total)\n    if internal.structure.selected is None or len(internal.probe_expressions) != 2:\n        return replace(\n            internal,\n            passed=False,\n            reason='independent_terminal_probe_verification_unavailable',\n            oracle_calls_total=oracle_calls_total,\n        )\n\n    terminal_probe_exact = 0\n    try:\n        selected = internal.structure.selected\n        for context in terminal:\n            for index, spec in enumerate(selected.program.interventions):\n                intervened = spec.apply(context, schema.field_names)\n                if _context_key(schema, intervened) in learning_query_keys:\n                    raise ValueError('terminal_contexts must be disjoint from all oracle query inputs used for learning')\n                if context_validator is not None and not bool(context_validator(intervened)):\n                    raise ValueError('terminal intervention contexts must satisfy context_validator')\n                expected_probe = tracked_oracle(intervened)\n                semantic_vector_key((expected_probe,))\n                actual_probe = evaluate_expr(internal.probe_expressions[index], context)\n                semantic_vector_key((actual_probe,))\n                terminal_probe_exact += int(_equivalent(actual_probe, expected_probe))\n    except ValueError as exc:\n        if 'disjoint' in str(exc):\n            raise\n        return replace(\n            internal,\n            passed=False,\n            final_validation_cases=len(terminal),\n            final_validation_exact=0,\n            reason='independent_terminal_probe_verification_error',\n            oracle_calls_total=oracle_calls_total,\n            terminal_probe_validation_cases=len(terminal) * 2,\n            terminal_probe_validation_exact=terminal_probe_exact,\n        )\n    except Exception:\n        return replace(\n            internal,\n            passed=False,\n            final_validation_cases=len(terminal),\n            final_validation_exact=0,\n            reason='independent_terminal_probe_verification_error',\n            oracle_calls_total=oracle_calls_total,\n            terminal_probe_validation_cases=len(terminal) * 2,\n            terminal_probe_validation_exact=terminal_probe_exact,\n        )\n\n    if terminal_probe_exact != len(terminal) * 2:\n        return replace(\n            internal,\n            passed=False,\n            final_validation_cases=len(terminal),\n            final_validation_exact=0,\n            reason='independent_terminal_probe_verification_failed',\n            oracle_calls_total=oracle_calls_total,\n            terminal_probe_validation_cases=len(terminal) * 2,\n            terminal_probe_validation_exact=terminal_probe_exact,\n        )\n\n    exact = 0\n    try:\n        for context in terminal:\n            expected = tracked_oracle(context)\n            semantic_vector_key((expected,))\n            actual = evaluate_expr(internal.expression, context)\n            semantic_vector_key((actual,))\n            exact += int(_equivalent(actual, expected))\n    except Exception:\n        return replace(\n            internal,\n            passed=False,\n            final_validation_cases=len(terminal),\n            final_validation_exact=exact,\n            reason='independent_terminal_verification_error',\n            oracle_calls_total=oracle_calls_total,\n            terminal_probe_validation_cases=len(terminal) * 2,\n            terminal_probe_validation_exact=terminal_probe_exact,\n        )\n\n    if exact != len(terminal):\n        return replace(\n            internal,\n            passed=False,\n            final_validation_cases=len(terminal),\n            final_validation_exact=exact,\n            reason='independent_terminal_verification_failed',\n            oracle_calls_total=oracle_calls_total,\n            terminal_probe_validation_cases=len(terminal) * 2,\n            terminal_probe_validation_exact=terminal_probe_exact,\n        )\n\n    return replace(\n        internal,\n        passed=True,\n        final_validation_cases=len(terminal),\n        final_validation_exact=exact,\n        reason='contextual_program_synthesized_terminally_verified',\n        oracle_calls_total=oracle_calls_total,\n        terminal_probe_validation_cases=len(terminal) * 2,\n        terminal_probe_validation_exact=terminal_probe_exact,\n    )\n"""
    if old_tail in text:
        assert text.count(old_tail) == 1
        text = text.replace(old_tail, new_tail, 1)
    elif 'terminal_probe_exact = 0' not in text:
        raise SystemExit('R2.66 terminal-authority tail changed concurrently')
    path.write_text(text)


if __name__ == '__main__':
    patch_core()
    patch_public()
    print('R266_UNIFIED_EVIDENCE_AUTHORITY_PATCH_APPLIED')
