from pathlib import Path

path=Path('research/r268_external_transfer.py')
text=path.read_text()
old="""    validation_values=(3.0,4.0,5.0,6.0)\n    discovery_rows=tuple(itertools.product(discovery_values,repeat=4))\n    validation_rows=tuple(itertools.product(validation_values,repeat=4))\n    discovery=discovery_rows[:220]\n    validation=validation_rows[:24]\n"""
new="""    validation_values=(3.0,4.0,5.0,6.0)\n    discovery_rows=tuple(itertools.product(discovery_values,repeat=4))\n    # Single-parity q-ary code: every pair of rows differs in at least two\n    # coordinates, so deleting/overwriting any one coordinate leaves an\n    # injective projection.  Therefore every legal single-field intervention\n    # produces 24 distinct validation oracle inputs as well as distinct bases.\n    validation_rows=tuple(\n        (validation_values[i],validation_values[j],validation_values[k],validation_values[(-i-j-k)%4])\n        for i,j,k in itertools.product(range(4),repeat=3)\n    )\n    discovery=discovery_rows[:220]\n    validation=validation_rows[:24]\n"""
if text.count(old)!=1: raise SystemExit(f'external validation anchor count != 1: {text.count(old)}')
path.write_text(text.replace(old,new,1))
print('R268_PROJECTION_UNIQUE_EXTERNAL_VALIDATION_APPLIED')
