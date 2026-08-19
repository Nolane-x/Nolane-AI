from pathlib import Path

external = Path('research/r268_external_transfer.py')
text = external.read_text()
old = """    values=(-2.0,-1.0,1.0,2.0)\n    rows=tuple(itertools.product(values,repeat=4))\n    discovery=rows[:220];validation=rows[220:244]\n"""
new = """    values=(-2.0,-1.0,1.0,2.0)\n    rows=tuple(itertools.product(values,repeat=4))\n    discovery=rows[:220]\n    # Validation uses a numerically disjoint non-zero domain. With the single\n    # intervention anchor 0.0 this keeps both base and intervention oracle\n    # inputs fresh relative to the complete discovery query universe.\n    validation_values=(-4.0,-3.0,3.0,4.0)\n    validation_rows=tuple(itertools.product(validation_values,repeat=4))\n    validation=validation_rows[:24]\n"""
if text.count(old) != 1:
    raise SystemExit(f'external validation anchor count != 1: {text.count(old)}')
external.write_text(text.replace(old, new, 1))

alias = Path('tests/test_r268_alias_order_invariance.py')
text = alias.read_text()
old = """VALIDATION = (\n    {'a': 1.0, 'b': 2.0},\n    {'a': 2.0, 'b': 3.0},\n    {'a': 4.0, 'b': 1.0},\n)\n"""
new = """VALIDATION = (\n    {'a': 5.0, 'b': 7.0},\n    {'a': 7.0, 'b': 5.0},\n    {'a': 11.0, 'b': 13.0},\n)\n"""
if text.count(old) != 1:
    raise SystemExit(f'alias validation anchor count != 1: {text.count(old)}')
alias.write_text(text.replace(old, new, 1))

print('R268_DISJOINT_VALIDATION_FIXTURES_APPLIED')
