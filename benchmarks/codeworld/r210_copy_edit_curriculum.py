from __future__ import annotations

import random
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from cogcoder.r210_copy_edit_features import FailureProbe, enumerate_copy_edit_candidates
from cogcoder.r29_patch_model import PatchCandidate, RepositorySnapshot, patch_fingerprint
from cogcoder.r29_patch_search import VerificationResult

ARITHMETIC = ('+', '-', '*', '/')
COMPARISON = ('<', '<=', '>', '>=')


@dataclass(frozen=True, slots=True)
class CopyEditTrainingRow:
    template_seed: int
    family: str
    language: str
    function_name: str
    source: str
    probes: tuple[FailureProbe, ...]
    candidates: tuple[PatchCandidate, ...]
    gold_index: int

    def public_record(self) -> dict[str, object]:
        return {
            'family': self.family,
            'language': self.language,
            'source': self.source,
            'probes': tuple((p.inputs, p.observed, p.expected, p.is_boolean) for p in self.probes),
            'candidate_count': len(self.candidates),
        }


@dataclass(frozen=True, slots=True)
class R210HeldoutCase:
    template_seed: int
    family: str
    language: str
    function_name: str
    source: str
    probes: tuple[FailureProbe, ...]
    snapshot: RepositorySnapshot
    candidates: tuple[PatchCandidate, ...]
    evaluator: Callable[[RepositorySnapshot, PatchCandidate], VerificationResult]
    expected_patch_fingerprint: str
    gold_index: int
    budget: int = 2

    def public_record(self) -> dict[str, object]:
        return {
            'family': self.family,
            'language': self.language,
            'source': self.source,
            'probes': tuple((p.inputs, p.observed, p.expected, p.is_boolean) for p in self.probes),
            'candidate_count': len(self.candidates),
            'budget': self.budget,
        }


def _apply_operator(operator: str, a: float, b: float) -> float:
    if operator == '+':
        return a + b
    if operator == '-':
        return a - b
    if operator == '*':
        return a * b
    if operator == '/':
        return a / b
    if operator == '<':
        return float(a < b)
    if operator == '<=':
        return float(a <= b)
    if operator == '>':
        return float(a > b)
    if operator == '>=':
        return float(a >= b)
    raise ValueError(operator)


def _distinct_arithmetic_pairs(rng: random.Random) -> tuple[tuple[float, float], tuple[float, float]]:
    for _ in range(100):
        pairs = (
            (float(rng.randint(-7, 7) or 3), float(rng.choice([-5, -4, -3, -2, -1, 1, 2, 3, 4, 5]))),
            (float(rng.randint(-7, 7) or -2), float(rng.choice([-5, -4, -3, -2, -1, 1, 2, 3, 4, 5]))),
        )
        signatures = {
            tuple(round(_apply_operator(op, a, b), 8) for a, b in pairs)
            for op in ARITHMETIC
        }
        if len(signatures) == len(ARITHMETIC):
            return pairs
    raise RuntimeError('failed to construct discriminative arithmetic probes')


def _probe_pairs(family: str, rng: random.Random) -> tuple[tuple[float, float], tuple[float, float]]:
    if family == 'arithmetic':
        return _distinct_arithmetic_pairs(rng)
    base = float(rng.randint(-6, 6))
    gap = float(rng.randint(1, 5))
    return ((base, base), (base, base + gap))


def _render_source(language: str, function_name: str, operator: str, params: tuple[str, str] = ('left', 'right')) -> str:
    left, right = params
    if language == 'python':
        return f'def {function_name}({left}, {right}):\n    return {left} {operator} {right}\n'
    if language == 'javascript':
        return f'function {function_name}({left}, {right}) {{\n  return {left} {operator} {right};\n}}\n'
    raise ValueError(language)


def _make_row(*, template_seed: int, family: str, language: str, prefix: str, params: tuple[str, str] = ('left', 'right')) -> CopyEditTrainingRow:
    rng = random.Random(template_seed)
    operators = ARITHMETIC if family == 'arithmetic' else COMPARISON
    correct = operators[template_seed % len(operators)]
    bug_choices = [op for op in operators if op != correct]
    bug = bug_choices[rng.randrange(len(bug_choices))]
    function_name = f'{prefix}_{family[:3]}_{template_seed}'
    source = _render_source(language, function_name, bug, params=params)
    candidates = enumerate_copy_edit_candidates(
        source,
        language=language,
        target_path='app.py' if language == 'python' else 'app.js',
        candidate_prefix=f'{prefix}-',
    )
    pairs = _probe_pairs(family, rng)
    probes = tuple(
        FailureProbe(
            (a, b),
            observed=_apply_operator(bug, a, b),
            expected=_apply_operator(correct, a, b),
            is_boolean=family == 'comparison',
        )
        for a, b in pairs
    )
    return CopyEditTrainingRow(
        template_seed=template_seed,
        family=family,
        language=language,
        function_name=function_name,
        source=source,
        probes=probes,
        candidates=candidates,
        gold_index=operators.index(correct),
    )


def build_r210_training_rows(*, seed: int = 210, rows_per_family: int = 192) -> tuple[CopyEditTrainingRow, ...]:
    rows: list[CopyEditTrainingRow] = []
    for family_index, family in enumerate(('arithmetic', 'comparison')):
        start = seed * 10_000 + family_index * 100_000
        for index in range(rows_per_family):
            rows.append(
                _make_row(
                    template_seed=start + index,
                    family=family,
                    language='python',
                    prefix='train',
                )
            )
    return tuple(rows)


class _JavaScriptEvaluator:
    def __init__(self, function_name: str, probes: tuple[FailureProbe, ...]) -> None:
        node = shutil.which('node')
        if node is None:
            raise RuntimeError('Node.js is required for R2.10 heldout protocol')
        self.node = node
        self.function_name = function_name
        self.probes = probes

    @staticmethod
    def _js_value(value: float, is_boolean: bool) -> str:
        if is_boolean:
            return 'true' if bool(value) else 'false'
        return repr(float(value))

    def _test_source(self, *, all_probes: bool) -> str:
        selected = self.probes if all_probes else self.probes[:1]
        lines = ["const fs=require('fs');", "eval(fs.readFileSync('app.js','utf8'));" ]
        for probe in selected:
            a, b = probe.inputs[:2]
            expected = self._js_value(probe.expected, probe.is_boolean)
            if probe.is_boolean:
                lines.append(f"if ({self.function_name}({a!r},{b!r}) !== {expected}) process.exit(1);")
            else:
                lines.append(
                    f"if (Math.abs({self.function_name}({a!r},{b!r}) - ({expected})) > 1e-8) process.exit(1);"
                )
        return '\n'.join(lines) + '\n'

    def __call__(self, patched: RepositorySnapshot, candidate: PatchCandidate) -> VerificationResult:
        with tempfile.TemporaryDirectory(prefix='nolane-r210-') as tmp:
            root = Path(tmp)
            for relative, content in patched.files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding='utf-8')
            (root / 'target_test.js').write_text(self._test_source(all_probes=False), encoding='utf-8')
            (root / 'full_test.js').write_text(self._test_source(all_probes=True), encoding='utf-8')
            target = subprocess.run([self.node, 'target_test.js'], cwd=root, capture_output=True, text=True, timeout=4)
            full = subprocess.run([self.node, 'full_test.js'], cwd=root, capture_output=True, text=True, timeout=4)
        target_ok = target.returncode == 0
        full_ok = full.returncode == 0
        return VerificationResult(
            targeted_tests_passed=int(target_ok),
            targeted_tests_total=1,
            full_tests_passed=full_ok,
            verifier_score=1.0 if full_ok else (0.7 if target_ok else 0.0),
            success=target_ok and full_ok,
            observations=(() if target_ok else ('target-failed',)) + (() if full_ok else ('full-failed',)),
            regression_detected=target_ok and not full_ok,
        )


def build_r210_heldout_cases(*, seed: int = 9210, cases_per_family: int = 24, identifier_variant: str = 'base') -> tuple[R210HeldoutCase, ...]:
    cases: list[R210HeldoutCase] = []
    for family_index, family in enumerate(('arithmetic', 'comparison')):
        start = seed * 10_000 + family_index * 100_000
        for index in range(cases_per_family):
            params = ('left', 'right') if identifier_variant == 'base' else ('sourceValue', 'otherValue')
            prefix = 'heldout' if identifier_variant == 'base' else 'renamed'
            row = _make_row(
                template_seed=start + index,
                family=family,
                language='javascript',
                prefix=prefix,
                params=params,
            )
            expected = row.candidates[row.gold_index]
            snapshot = RepositorySnapshot({'app.js': row.source})
            cases.append(
                R210HeldoutCase(
                    template_seed=row.template_seed,
                    family=row.family,
                    language=row.language,
                    function_name=row.function_name,
                    source=row.source,
                    probes=row.probes,
                    snapshot=snapshot,
                    candidates=row.candidates,
                    evaluator=_JavaScriptEvaluator(row.function_name, row.probes),
                    expected_patch_fingerprint=patch_fingerprint(expected),
                    gold_index=row.gold_index,
                    budget=2,
                )
            )
    return tuple(cases)
