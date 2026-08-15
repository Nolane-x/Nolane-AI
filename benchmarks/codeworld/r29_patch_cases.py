from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from cogcoder.r28_repo_world import RepoEdge, RepoNode, RepoWorldGraph
from cogcoder.r29_patch_model import PatchCandidate, RepositorySnapshot, TextEdit, patch_fingerprint
from cogcoder.r29_patch_search import VerificationResult


@dataclass(frozen=True, slots=True)
class R29PatchCase:
    name: str
    language: str
    snapshot: RepositorySnapshot
    initial_candidates: tuple[PatchCandidate, ...]
    evaluator: Callable[[RepositorySnapshot, PatchCandidate], VerificationResult]
    refine: Callable[[PatchCandidate, VerificationResult], Iterable[PatchCandidate]]
    graph: RepoWorldGraph
    expected_patch_fingerprint: str
    budget: int = 8

    def public_record(self) -> dict[str, object]:
        return {
            'name': self.name,
            'language': self.language,
            'budget': self.budget,
            'initial_candidate_count': len(self.initial_candidates),
            'file_count': len(self.snapshot.files),
        }


class _ExecutableEvaluator:
    def __init__(self, target_commands: tuple[tuple[str, ...], ...], full_command: tuple[str, ...]) -> None:
        self.target_commands = target_commands
        self.full_command = full_command

    def _resolve(self, command: tuple[str, ...]) -> list[str]:
        resolved: list[str] = []
        for token in command:
            if token == '{python}':
                resolved.append(sys.executable)
            elif token == '{node}':
                node = shutil.which('node')
                if node is None:
                    raise RuntimeError('node runtime required by locked R2.9 protocol')
                resolved.append(node)
            else:
                resolved.append(token)
        return resolved

    def _run(self, root: Path, command: tuple[str, ...]) -> tuple[bool, str]:
        completed = subprocess.run(
            self._resolve(command),
            cwd=root,
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        output = (completed.stdout + '\n' + completed.stderr).strip()
        return completed.returncode == 0, output[-600:]

    def __call__(self, patched: RepositorySnapshot, candidate: PatchCandidate) -> VerificationResult:
        with tempfile.TemporaryDirectory(prefix='nolane-r29-') as tmp:
            root = Path(tmp)
            for relative, content in patched.files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding='utf-8')

            targeted = [self._run(root, command) for command in self.target_commands]
            targeted_passed = sum(int(ok) for ok, _ in targeted)
            full_ok, full_output = self._run(root, self.full_command)
            fraction = targeted_passed / len(targeted) if targeted else 0.0
            verifier_score = min(1.0, 0.9 * fraction + (0.1 if full_ok else 0.0))
            observations = tuple(
                [f'target-{index}-failed:{output}' for index, (ok, output) in enumerate(targeted) if not ok]
                + ([f'full-regression:{full_output}'] if not full_ok else [])
            )
            success = targeted_passed == len(targeted) and full_ok
            return VerificationResult(
                targeted_tests_passed=targeted_passed,
                targeted_tests_total=len(targeted),
                full_tests_passed=full_ok,
                verifier_score=verifier_score,
                success=success,
                observations=observations,
                regression_detected=not full_ok and targeted_passed == len(targeted),
            )


def _graph(nodes: tuple[str, ...], edges: tuple[tuple[str, str, str], ...] = ()) -> RepoWorldGraph:
    graph = RepoWorldGraph()
    for node in nodes:
        graph.add_node(RepoNode(node, 'symbol', path=node))
    for source, target, kind in edges:
        graph.add_edge(RepoEdge(source, target, kind))
    return graph


def _python_refinement_case(prefix: str) -> R29PatchCase:
    snapshot = RepositorySnapshot(
        {
            'app.py': 'def clamp(value, low, high):\n    return min(value, low)\n',
            'target_low.py': 'from app import clamp\nassert clamp(-2, 0, 10) == 0\n',
            'target_high.py': 'from app import clamp\nassert clamp(12, 0, 10) == 10\n',
            'full_test.py': (
                'from app import clamp\n'
                'assert clamp(-2, 0, 10) == 0\n'
                'assert clamp(5, 0, 10) == 5\n'
                'assert clamp(12, 0, 10) == 10\n'
            ),
        }
    )
    initial = PatchCandidate(
        f'{prefix}partial-clamp',
        (TextEdit('app.py', 2, 3, '    return max(value, low)\n'),),
        provenance='symbolic-bound-fix',
        targeted_nodes=frozenset({'app'}),
        proposal_score=0.3,
    )
    correct = PatchCandidate(
        f'{prefix}refined-clamp',
        (TextEdit('app.py', 2, 3, '    return max(low, min(value, high))\n'),),
        parent_candidate_id=initial.candidate_id,
        provenance='execution-refinement',
        targeted_nodes=frozenset({'app'}),
        proposal_score=0.2,
    )

    def refine(candidate: PatchCandidate, result: VerificationResult):
        if result.success:
            return ()
        if any(item.startswith('target-1-failed:') for item in result.observations):
            return (correct,)
        return ()

    return R29PatchCase(
        'python-execution-refinement',
        'python',
        snapshot,
        (initial,),
        _ExecutableEvaluator((('{python}', 'target_low.py'), ('{python}', 'target_high.py')), ('{python}', 'full_test.py')),
        refine,
        _graph(('app', 'target_low', 'target_high', 'full_test'), (
            ('target_low', 'app', 'tests'),
            ('target_high', 'app', 'tests'),
            ('full_test', 'app', 'tests'),
        )),
        patch_fingerprint(correct),
        budget=4,
    )


def _javascript_risk_case(prefix: str) -> R29PatchCase:
    snapshot = RepositorySnapshot(
        {
            'core.js': 'exports.scale = x => x * 2;\n',
            'adapter.js': "const { scale } = require('./core');\nexports.userScale = x => scale(x);\n",
            'target_test.js': "const { userScale } = require('./adapter');\nif (userScale(3) !== 9) process.exit(1);\n",
            'full_test.js': (
                "const { scale } = require('./core');\n"
                "const { userScale } = require('./adapter');\n"
                'if (scale(4) !== 8) process.exit(1);\n'
                'if (userScale(3) !== 9) process.exit(1);\n'
            ),
        }
    )
    low = PatchCandidate(
        f'{prefix}adapter-only',
        (TextEdit('adapter.js', 2, 3, 'exports.userScale = x => scale(x) + x;\n'),),
        targeted_nodes=frozenset({'adapter'}),
        proposal_score=0.0,
        provenance='local-adapter-fix',
    )
    high = PatchCandidate(
        f'{prefix}shared-core',
        (
            TextEdit('core.js', 2, 2, 'exports.userScaleCore = x => x * 3;\n'),
            TextEdit(
                'adapter.js',
                1,
                3,
                "const { userScaleCore } = require('./core');\nexports.userScale = x => userScaleCore(x);\n",
            ),
        ),
        targeted_nodes=frozenset({'core', 'adapter'}),
        proposal_score=0.0,
        provenance='shared-core-fix',
    )
    graph = _graph(
        ('core', 'adapter', 'target_test', 'full_test'),
        (
            ('adapter', 'core', 'depends_on'),
            ('target_test', 'adapter', 'tests'),
            ('full_test', 'adapter', 'tests'),
            ('full_test', 'core', 'tests'),
        ),
    )
    return R29PatchCase(
        'javascript-low-blast-radius',
        'javascript',
        snapshot,
        (high, low),
        _ExecutableEvaluator((('{node}', 'target_test.js'),), ('{node}', 'full_test.js')),
        lambda candidate, result: (),
        graph,
        patch_fingerprint(low),
        budget=3,
    )


def _python_duplicate_case(prefix: str) -> R29PatchCase:
    snapshot = RepositorySnapshot(
        {
            'maths.py': 'def add(a, b):\n    return a - b\n',
            'target_test.py': 'from maths import add\nassert add(7, 5) == 12\n',
            'full_test.py': 'from maths import add\nassert add(7, 5) == 12\nassert add(-2, 2) == 0\n',
        }
    )
    edit = (TextEdit('maths.py', 2, 3, '    return a + b\n'),)
    correct = PatchCandidate(
        f'{prefix}correct-a', edit, targeted_nodes=frozenset({'maths'}), proposal_score=0.3
    )
    duplicate = PatchCandidate(
        f'{prefix}correct-b', edit, targeted_nodes=frozenset({'maths'}), proposal_score=0.3
    )
    decoy = PatchCandidate(
        f'{prefix}decoy',
        (TextEdit('maths.py', 2, 3, '    return abs(a) + abs(b)\n'),),
        targeted_nodes=frozenset({'maths'}),
        proposal_score=0.0,
    )
    return R29PatchCase(
        'python-canonical-deduplication',
        'python',
        snapshot,
        (correct, duplicate, decoy),
        _ExecutableEvaluator((('{python}', 'target_test.py'),), ('{python}', 'full_test.py')),
        lambda candidate, result: (),
        _graph(('maths', 'target_test', 'full_test'), (
            ('target_test', 'maths', 'tests'),
            ('full_test', 'maths', 'tests'),
        )),
        patch_fingerprint(correct),
        budget=3,
    )


def _javascript_regression_case(prefix: str) -> R29PatchCase:
    snapshot = RepositorySnapshot(
        {
            'calc.js': 'exports.abs = x => x;\n',
            'target_test.js': "const { abs } = require('./calc');\nif (abs(-3) !== 3) process.exit(1);\n",
            'full_test.js': (
                "const { abs } = require('./calc');\n"
                'if (abs(-3) !== 3) process.exit(1);\n'
                'if (abs(3) !== 3) process.exit(1);\n'
            ),
        }
    )
    tempting = PatchCandidate(
        f'{prefix}negate',
        (TextEdit('calc.js', 1, 2, 'exports.abs = x => -x;\n'),),
        targeted_nodes=frozenset({'calc'}),
        proposal_score=1.0,
        provenance='target-only-fix',
    )
    correct = PatchCandidate(
        f'{prefix}math-abs',
        (TextEdit('calc.js', 1, 2, 'exports.abs = x => Math.abs(x);\n'),),
        parent_candidate_id=tempting.candidate_id,
        targeted_nodes=frozenset({'calc'}),
        proposal_score=0.0,
        provenance='regression-driven-refinement',
    )

    def refine(candidate: PatchCandidate, result: VerificationResult):
        if result.regression_detected:
            return (correct,)
        return ()

    return R29PatchCase(
        'javascript-regression-blocks-false-terminal',
        'javascript',
        snapshot,
        (tempting,),
        _ExecutableEvaluator((('{node}', 'target_test.js'),), ('{node}', 'full_test.js')),
        refine,
        _graph(('calc', 'target_test', 'full_test'), (
            ('target_test', 'calc', 'tests'),
            ('full_test', 'calc', 'tests'),
        )),
        patch_fingerprint(correct),
        budget=4,
    )


def locked_r29_cases(*, id_prefix: str = '') -> tuple[R29PatchCase, ...]:
    return (
        _python_refinement_case(id_prefix),
        _javascript_risk_case(id_prefix),
        _python_duplicate_case(id_prefix),
        _javascript_regression_case(id_prefix),
    )
