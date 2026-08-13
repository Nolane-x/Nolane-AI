# Frontier >100B Evaluation Contract

This directory defines scoring and provenance rules for comparing Nolane with frontier systems. It intentionally does **not** claim that the local FIGG-19 benchmark is already proven hard for models above 100B parameters. That label is forbidden until a named >100B reference model is actually run under a locked protocol with recorded budget and score.

## Benchmark families to import or run externally

### ARC-AGI-2

Primary source: https://arcprize.org/arc-agi/2
Competition: https://arcprize.org/competitions/2026/arc-agi-2

Use exact grid equality and the official pass@2-compatible rule: at most two predicted outputs per test grid, with a task scored correct if one output exactly matches the reference. Private evaluation data is not vendored here.

### Humanity's Last Exam / HLE-Verified

Primary HLE paper: https://arxiv.org/abs/2501.14249
HLE-Verified paper: https://arxiv.org/abs/2602.13964

Use closed-answer scoring only when the benchmark supplies an unambiguous target. The local scorer is deliberately conservative: whitespace/case normalization only, with no model-based semantic judging.

### FrontierMath

Primary paper: https://arxiv.org/abs/2411.04872
Benchmark information: https://epoch.ai/frontiermath

A FrontierMath-style run must use the supplied benchmark verifier or an equivalently exact executable checker. Free-form LLM grading is not accepted as evidence.

### Terminal-Bench / hard coding

Primary repository: https://github.com/harbor-framework/terminal-bench

Use sandboxed execution and task test scripts. For contest-style code benchmarks, use an offline judge with fixed resource limits and hidden tests.

## Claim boundary

A comparison record may set `hard_for_gt100b: true` only when `reference_runs` contains at least one real evaluated model with:

- a non-empty model/version name;
- `parameter_count > 100_000_000_000`;
- `evaluated: true`;
- a finite measured score;
- a non-empty compute/token/time budget;
- a locked protocol SHA-256.

This makes "hard for >100B" a measured property rather than a marketing label.
