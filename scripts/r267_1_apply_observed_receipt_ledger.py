from __future__ import annotations

from pathlib import Path


path = Path('cogcoder/r267_three_probe_causal_composition.py')
text = path.read_text()

# Exact R2.67.1 production surfaces: keep the patch narrow and fail if peers
# changed any targeted receipt path concurrently.
old = """    selected = structure.selected
    planned_probe_validation_cases = len(validation) * len(selected.profiles)
    probe_canonical: list[Expr] = []
    probe_external: list[Expr] = []
    probe_counts: list[int] = []
    probe_validation_exact = 0
"""
new = """    selected = structure.selected
    planned_probe_validation_cases = len(validation) * len(selected.profiles)
    probe_canonical: list[Expr] = []
    probe_external: list[Expr] = []
    probe_counts: list[int] = []
    probe_validation_cases = 0
    probe_validation_exact = 0
"""
if old not in text:
    raise SystemExit('selected/probe ledger initialization surface changed concurrently')
text = text.replace(old, new, 1)

old = """        for context, expected in zip(validation, profile.validation_outputs, strict=True):
            try:
"""
new = """        for context, expected in zip(validation, profile.validation_outputs, strict=True):
            probe_validation_cases += 1
            try:
"""
if old not in text:
    raise SystemExit('probe validation loop surface changed concurrently')
text = text.replace(old, new, 1)

# Once a triplet is selected, every receipt must report observed probe cases,
# never the planned denominator. Successful paths naturally reach the plan.
selected_index = text.index('    selected = structure.selected\n')
prefix = text[:selected_index]
suffix = text[selected_index:]
count = suffix.count('probe_validation_cases=planned_probe_validation_cases,')
if count < 1:
    raise SystemExit('planned probe receipt fields not found')
suffix = suffix.replace(
    'probe_validation_cases=planned_probe_validation_cases,',
    'probe_validation_cases=probe_validation_cases,',
)
text = prefix + suffix

# No final/terminal base case has been attempted before terminal verification.
for reason in ('probe_synthesis_failed', 'probe_validation_failed', 'substituted_validation_failed'):
    marker = f"reason='{reason}'"
    idx = text.index(marker)
    start = text.rfind('return ThreeProbeCompositionReceipt(', 0, idx)
    end = text.index('            )', idx) + len('            )')
    block = text[start:end]
    if 'final_validation_cases=len(terminal),' not in block:
        raise SystemExit(f'{reason} final-case surface changed concurrently')
    block = block.replace('final_validation_cases=len(terminal),', 'final_validation_cases=0,')
    text = text[:start] + block + text[end:]

# Structure failure also happens before any probe or terminal/final attempt.
marker = "reason='structure_discovery_failed'"
idx = text.index(marker)
start = text.rfind('return ThreeProbeCompositionReceipt(', 0, idx)
end = text.index('        )', idx) + len('        )')
block = text[start:end]
if 'probe_validation_cases=0,' not in block or 'final_validation_cases=len(terminal),' not in block:
    raise SystemExit('structure failure receipt surface changed concurrently')
block = block.replace('final_validation_cases=len(terminal),', 'final_validation_cases=0,')
text = text[:start] + block + text[end:]

old = """    terminal_calls = 0
    terminal_probe_exact = 0
    final_exact = 0
"""
new = """    terminal_calls = 0
    terminal_probe_cases = 0
    terminal_probe_exact = 0
    final_cases = 0
    final_exact = 0
"""
if old not in text:
    raise SystemExit('terminal ledger initialization surface changed concurrently')
text = text.replace(old, new, 1)

old = """            for index, profile in enumerate(selected.profiles):
                intervened = profile.intervention.apply(context, schema.field_names)
"""
new = """            for index, profile in enumerate(selected.profiles):
                terminal_probe_cases += 1
                intervened = profile.intervention.apply(context, schema.field_names)
"""
if old not in text:
    raise SystemExit('terminal probe attempt surface changed concurrently')
text = text.replace(old, new, 1)

old = """            expected = terminal_oracle(context)
            actual = _finite_json_value(evaluate_expr(expression, context))
"""
new = """            final_cases += 1
            expected = terminal_oracle(context)
            actual = _finite_json_value(evaluate_expr(expression, context))
"""
if old not in text:
    raise SystemExit('terminal final attempt surface changed concurrently')
text = text.replace(old, new, 1)

terminal_index = text.index('    terminal_calls = 0\n')
prefix = text[:terminal_index]
suffix = text[terminal_index:]
if 'terminal_probe_validation_cases=len(terminal) * 3,' not in suffix:
    raise SystemExit('planned terminal probe receipt fields not found')
suffix = suffix.replace(
    'terminal_probe_validation_cases=len(terminal) * 3,',
    'terminal_probe_validation_cases=terminal_probe_cases,',
)
suffix = suffix.replace(
    'final_validation_cases=len(terminal),',
    'final_validation_cases=final_cases,',
)
suffix = suffix.replace(
    '    terminal_probe_cases = len(terminal) * 3\n    if terminal_probe_exact != terminal_probe_cases:\n',
    '    expected_terminal_probe_cases = len(terminal) * 3\n    if terminal_probe_cases != expected_terminal_probe_cases or terminal_probe_exact != terminal_probe_cases:\n',
    1,
)
# Any later receipt formerly using the planned terminal count now reports the
# actual attempted count; success still equals the expected total.
suffix = suffix.replace(
    'terminal_probe_validation_cases=terminal_probe_cases,',
    'terminal_probe_validation_cases=terminal_probe_cases,',
)
text = prefix + suffix

path.write_text(text)
print('R267_1_OBSERVED_RECEIPT_LEDGER_PATCH_APPLIED', count)
