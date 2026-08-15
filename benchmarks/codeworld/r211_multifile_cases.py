from __future__ import annotations

import random
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from cogcoder.r28_repo_world import RepoEdge, RepoNode, RepoWorldGraph
from cogcoder.r210_copy_edit_features import FailureProbe, enumerate_copy_edit_candidates
from cogcoder.r211_counterfactual_localizer import SymbolSlice, TestCoverageObservation
from cogcoder.r29_patch_model import PatchCandidate, RepositorySnapshot, patch_fingerprint
from cogcoder.r29_patch_search import VerificationResult

ARITHMETIC = ('+', '-', '*', '/')
COMPARISON = ('<', '<=', '>', '>=')


def _apply(operator: str, a: float, b: float) -> float:
    if operator == '+': return a + b
    if operator == '-': return a - b
    if operator == '*': return a * b
    if operator == '/': return a / b
    if operator == '<': return float(a < b)
    if operator == '<=': return float(a <= b)
    if operator == '>': return float(a > b)
    if operator == '>=': return float(a >= b)
    raise ValueError(operator)


def _js_expected(value: float, boolean: bool) -> str:
    if boolean:
        return 'true' if bool(value) else 'false'
    return repr(float(value))


def _random_name(rng: random.Random, prefix: str) -> str:
    alphabet = 'abcdefghjkmnpqrstuvwxyz'
    return prefix + ''.join(rng.choice(alphabet) for _ in range(8))


def _render_provider(function_name: str, left: str, right: str, operator: str) -> str:
    return (
        f'function {function_name}({left}, {right}) {{\n'
        f'  return {left} {operator} {right};\n'
        '}\n'
        f'module.exports = {{ {function_name} }};\n'
    )


@dataclass(frozen=True, slots=True)
class R211Case:
    name: str
    family: str
    snapshot: RepositorySnapshot
    symbols: tuple[SymbolSlice, ...]
    graph: RepoWorldGraph
    failing_test_node: str
    probes: tuple[FailureProbe, ...]
    probes_by_node: dict[str, tuple[FailureProbe, ...]]
    coverage: tuple[TestCoverageObservation, ...]
    evaluator: Callable[[RepositorySnapshot, PatchCandidate], VerificationResult]
    gold_node_id: str
    gold_path: str
    gold_patch_fingerprint: str
    provider_count: int

    def public_record(self) -> dict[str, object]:
        return {
            'name': self.name,
            'family': self.family,
            'symbol_count': len(self.symbols),
            'provider_count': self.provider_count,
            'probe_count': len(self.probes),
            'coverage_tests': len(self.coverage),
        }


class _R211Evaluator:
    def __init__(self, probes: tuple[FailureProbe, ...]) -> None:
        node = shutil.which('node')
        if node is None:
            raise RuntimeError('Node.js required for R2.11 protocol')
        self.node = node
        self.probes = probes

    def _test_source(self, all_probes: bool) -> str:
        selected = self.probes if all_probes else self.probes[:1]
        lines = ["const { runAll } = require('./service');"]
        for probe in selected:
            a, b = probe.inputs[:2]
            expected = _js_expected(probe.expected, probe.is_boolean)
            lines.append(f'for (const value of runAll({a!r},{b!r})) {{')
            if probe.is_boolean:
                lines.append(f'  if (value !== {expected}) process.exit(1);')
            else:
                lines.append(f'  if (Math.abs(value - ({expected})) > 1e-8) process.exit(1);')
            lines.append('}')
        return '\n'.join(lines) + '\n'

    def __call__(self, patched: RepositorySnapshot, candidate: PatchCandidate) -> VerificationResult:
        with tempfile.TemporaryDirectory(prefix='nolane-r211-') as tmp:
            root = Path(tmp)
            for relative, content in patched.files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding='utf-8')
            (root / 'target_test.js').write_text(self._test_source(False), encoding='utf-8')
            (root / 'full_test.js').write_text(self._test_source(True), encoding='utf-8')
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


def build_r211_cases(
    *,
    seed: int = 21100,
    count: int = 64,
    providers: int = 8,
    offpath: int = 2,
    identity_variant: str = 'base',
) -> tuple[R211Case, ...]:
    if providers < 4:
        raise ValueError('providers must be >= 4')
    cases: list[R211Case] = []
    for case_index in range(count):
        rng = random.Random(seed + case_index * 7919)
        family = 'arithmetic' if case_index % 2 == 0 else 'comparison'
        operators = ARITHMETIC if family == 'arithmetic' else COMPARISON
        correct = operators[(seed + case_index) % len(operators)]
        bug = rng.choice([operator for operator in operators if operator != correct])
        target_index = rng.randrange(providers)
        boolean = family == 'comparison'
        pairs = ((3.0 + (case_index % 3), 2.0), (-2.0, 4.0 + (case_index % 2)))
        if family == 'arithmetic' and correct == '/':
            pairs = ((6.0, 2.0), (-8.0, 4.0))
        probes = tuple(
            FailureProbe(
                inputs=(a, b),
                observed=_apply(bug, a, b),
                expected=_apply(correct, a, b),
                is_boolean=boolean,
            )
            for a, b in pairs
        )

        files: dict[str, str] = {}
        symbols: list[SymbolSlice] = []
        graph = RepoWorldGraph()
        test_node = _random_name(rng, 't_')
        service_node = _random_name(rng, 's_')
        graph.add_node(RepoNode(test_node, 'test'))
        graph.add_node(RepoNode(service_node, 'symbol'))
        graph.add_edge(RepoEdge(test_node, service_node, 'tests'))
        require_lines: list[str] = []
        call_names: list[str] = []
        gold_node = ''
        gold_path = ''
        gold_patch = ''
        provider_nodes: list[str] = []
        probes_by_node: dict[str, tuple[FailureProbe, ...]] = {}

        for provider_index in range(providers):
            node_id = _random_name(rng, 'n_' if identity_variant == 'base' else 'q_')
            path = _random_name(rng, 'm_' if identity_variant == 'base' else 'z_') + '.js'
            fn = _random_name(rng, 'f_' if identity_variant == 'base' else 'r_')
            left = _random_name(rng, 'a_' if identity_variant == 'base' else 'x_')
            right = _random_name(rng, 'b_' if identity_variant == 'base' else 'y_')
            operator = bug if provider_index == target_index else correct
            source = _render_provider(fn, left, right, operator)
            files[path] = source
            symbols.append(SymbolSlice(node_id, path, source))
            graph.add_node(RepoNode(node_id, 'symbol', path=path))
            graph.add_edge(RepoEdge(service_node, node_id, 'calls'))
            provider_nodes.append(node_id)
            probes_by_node[node_id] = tuple(
                FailureProbe(
                    inputs=probe.inputs,
                    observed=_apply(operator, probe.inputs[0], probe.inputs[1]),
                    expected=probe.expected,
                    is_boolean=probe.is_boolean,
                )
                for probe in probes
            )
            alias = f'p{provider_index}'
            require_lines.append(f"const {{ {fn}: {alias} }} = require('./{path[:-3]}');")
            call_names.append(alias)
            if provider_index == target_index:
                candidates = enumerate_copy_edit_candidates(source, language='javascript', target_path=path, candidate_prefix='hidden-')
                gold_index = operators.index(correct)
                gold_node = node_id
                gold_path = path
                gold_patch = patch_fingerprint(candidates[gold_index])

        coverage_rows: list[TestCoverageObservation] = []
        target_node = provider_nodes[target_index]
        shadow_node = rng.choice([node for node in provider_nodes if node != target_node])
        # Target and one healthy shadow have identical failing/pass coverage.
        # Spectrum localization alone must therefore tie; differential runtime
        # behavior is required to break the ambiguity.
        for test_index in range(8):
            if test_index < 4:
                pool = [node for node in provider_nodes if node not in {target_node, shadow_node}]
                extras = rng.sample(pool, k=min(2, len(pool)))
                covered = frozenset([target_node, shadow_node, *extras])
                passed = False
            else:
                pool = [node for node in provider_nodes if node not in {target_node, shadow_node}]
                covered = frozenset(rng.sample(pool, k=min(4, len(pool))))
                passed = True
            coverage_rows.append(TestCoverageObservation(_random_name(rng, 'ct_'), covered, passed))

        service_source = '\n'.join(require_lines) + '\n' + (
            'function runAll(left, right) {\n'
            '  return [' + ', '.join(f'{name}(left, right)' for name in call_names) + '];\n'
            '}\nmodule.exports = { runAll };\n'
        )
        files['service.js'] = service_source

        for _ in range(offpath):
            node_id = _random_name(rng, 'o_' if identity_variant == 'base' else 'w_')
            path = _random_name(rng, 'd_' if identity_variant == 'base' else 'v_') + '.js'
            fn = _random_name(rng, 'd_')
            left = _random_name(rng, 'u_')
            right = _random_name(rng, 'v_')
            source = _render_provider(fn, left, right, bug)
            files[path] = source
            symbols.append(SymbolSlice(node_id, path, source))
            graph.add_node(RepoNode(node_id, 'symbol', path=path))

        # Public enumeration order is independently shuffled; target position carries no semantics.
        rng.shuffle(symbols)
        cases.append(
            R211Case(
                name=f'r211-{family}-{case_index}',
                family=family,
                snapshot=RepositorySnapshot(files),
                symbols=tuple(symbols),
                graph=graph,
                failing_test_node=test_node,
                probes=probes,
                probes_by_node=probes_by_node,
                coverage=tuple(coverage_rows),
                evaluator=_R211Evaluator(probes),
                gold_node_id=gold_node,
                gold_path=gold_path,
                gold_patch_fingerprint=gold_patch,
                provider_count=providers,
            )
        )
    return tuple(cases)
