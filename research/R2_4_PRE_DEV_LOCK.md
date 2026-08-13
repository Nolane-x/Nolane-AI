# R2.4 pre-DEV lock

Status: frozen before DEV.

Neural effective parameters: 78,779,253. New R2.4 neural parameters: 0.

Canonical GitHub blob identities:
- `cogcoder/longhorizon_world.py`: `4c8728231f5102ab3801c1e3b39c9c16613d5c5a`
- `cogcoder/sequence_refresh.py`: `c6d01e6db6810d37135a98224e5b8ebf69ed24ad`
- `cogcoder/kfigg24.py`: `9238c558d413f10e3cb9eceb0c7f8efe2fff935c`
- `scripts/measure_r24.py`: `6f36550543838a46e8dc74d92fdbad3f451eef6b`

Locked protocol:
- TRAIN seeds: 10000..10199, consumed for protocol selection.
- DEV seeds: 11000..11199, unopened at lock time.
- Final held-out seeds: 12000..12199, unopened at lock time.
- max_steps: 26.
- retry_budget: 2.
- public goal/action/observation interface only.

Locked TRAIN result:
- baseline: 66/200 = 33.0%.
- candidate: 190/200 = 95.0%.
- gain: +62.0 percentage points.
- requirement-change recovery: 92.5373%.
- transient recovery: 90.0990%.
- candidate blocked attempts: 0.
- candidate mean steps on solved episodes: 21.4211.

Admission thresholds:
- candidate solve rate >= 85%.
- gain >= +20 percentage points.
- requirement-change recovery >= 85%.
- transient recovery >= 85%.
- candidate blocked attempts = 0.

No candidate/source/protocol tuning is permitted after DEV is opened. High KFIGG-24 performance is evidence only for this bounded synthetic long-horizon replanning capability and does not establish broad autonomy or AGI.
