# Nolane CodeWorld Evaluation Contract

R2.7 changes the main research target from benchmark-specific abstraction to **general coding intelligence**. ARC remains useful as one abstraction probe, but it is not the target distribution.

## Capability axes

1. **Issue resolution / bug fixing** — real repository issues and tests.
2. **Feature implementation** — new behavior spanning existing modules.
3. **Large refactoring** — behavior-preserving, coordinated multi-file changes.
4. **Terminal/tool operation** — build, test, debug, package and environment tasks.
5. **Multilingual transfer** — Python, JavaScript/TypeScript, Java, Go, Rust, C/C++ and additional ecosystems.
6. **Multi-turn evolution** — keep a repository working as requirements change.
7. **Code generation/self-repair** — algorithmic generation, execution and repair.
8. **ML engineering** — experimental pipelines and model engineering as a distinct coding subdomain.

## Primary external gates

Use locked upstream revisions and official evaluators where available:

- SWE-bench Verified: https://www.swebench.com/verified.html
- Multi-SWE-bench: https://arxiv.org/abs/2504.02605
- FeatureBench: https://github.com/LiberCoders/FeatureBench
- SWE-Bench ProMax: https://arxiv.org/abs/2608.09802
- Terminal-Bench: https://github.com/harbor-framework/terminal-bench
- EvoCode-Bench: https://github.com/UniPat-AI/EvoCodeBench
- LiveCodeBench: https://github.com/LiveCodeBench/LiveCodeBench
- MLE-bench: https://github.com/openai/mle-bench

## Anti-overfit protocol

- Hidden tests and gold patches are evaluation-only.
- Development tasks may be used for debugging the harness, but consumed held-out results may not be tuned against.
- Every benchmark run records upstream revision, model SHA, runtime SHA, action/token/time budget and evaluator version.
- A candidate must improve more than one capability axis before it can be described as a broader coding upgrade.
- Multilingual claims require whole-repository tasks in multiple language ecosystems, not translated prompts alone.
- A high internal synthetic score is never substituted for an external result.

## Phase-A interpretation

The Phase-A controller curriculum is deliberately abstract. It tests whether one compact controller can learn the same software-engineering control policy across unseen `(language, task_type)` combinations. It does **not** test source-code generation quality, repository understanding or real-world issue resolution. Those are Phase-B gates.
