# R2.4 stage-3 freeze

This marker freezes R2.4 before its final held-out evaluation.

Canonical GitHub blob identities:
- `cogcoder/longhorizon_world.py`: `4c8728231f5102ab3801c1e3b39c9c16613d5c5a`
- `cogcoder/sequence_refresh.py`: `c6d01e6db6810d37135a98224e5b8ebf69ed24ad`
- `cogcoder/kfigg24.py`: `9238c558d413f10e3cb9eceb0c7f8efe2fff935c`
- `scripts/measure_r24.py`: `6f36550543838a46e8dc74d92fdbad3f451eef6b`

Protocol remains max_steps 26 and retry_budget 2.
Final held-out range: 12000..12199.
Admission thresholds remain candidate >=85%, difference >=20 percentage points, public requirement-change completion >=85%, transient-event completion >=85%, blocked attempts = 0.

No candidate source or protocol changes are allowed after this marker.
