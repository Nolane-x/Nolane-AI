from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Iterable

from .epistemic_program import EpistemicProgram, ProgramRegistry

_VERSION_TOKEN = re.compile(r'(\d+|[A-Za-z]+)')


def _version_key(version: str) -> tuple:
    parts = []
    for token in _VERSION_TOKEN.findall(str(version)):
        parts.append((0, int(token)) if token.isdigit() else (1, token.casefold()))
    return tuple(parts) or ((1, str(version).casefold()),)


@dataclass(frozen=True)
class SkillArtifact:
    name: str
    version: str
    program: EpistemicProgram
    demonstrations: tuple[tuple[int, int], ...]
    provenance_sha256: str
    source_uri: str
    validation_score: float
    successes: int = 0
    failures: int = 0
    validated: bool = True

    def __post_init__(self):
        if not self.name or not self.version or not self.provenance_sha256 or not self.source_uri:
            raise ValueError('skill identity and provenance fields must be non-empty')
        if self.program.name != self.name:
            raise ValueError('program name must match skill name')
        if not 0.0 <= float(self.validation_score) <= 1.0:
            raise ValueError('validation_score must be in [0,1]')
        if self.successes < 0 or self.failures < 0:
            raise ValueError('feedback counters must be non-negative')

    @property
    def competence(self) -> float:
        total = self.successes + self.failures
        return self.validation_score if total == 0 else self.successes / total


class SkillRegistry:
    trainable_parameter_count = 0

    def __init__(self, artifacts: Iterable[SkillArtifact] = ()):
        self._history: dict[str, dict[str, SkillArtifact]] = {}
        self._current: dict[str, str] = {}
        for artifact in artifacts:
            self.install(artifact)

    def install(self, artifact: SkillArtifact) -> SkillArtifact:
        versions = self._history.setdefault(artifact.name, {})
        previous = versions.get(artifact.version)
        if previous is not None:
            if previous.provenance_sha256 != artifact.provenance_sha256 or previous != artifact:
                raise ValueError('version provenance collision')
            return previous
        versions[artifact.version] = artifact
        current_version = self._current.get(artifact.name)
        if artifact.validated and (current_version is None or _version_key(artifact.version) > _version_key(current_version)):
            self._current[artifact.name] = artifact.version
        return artifact

    def has(self, name: str) -> bool:
        return name in self._current

    def current(self, name: str) -> SkillArtifact:
        if name not in self._current:
            raise KeyError(name)
        return self._history[name][self._current[name]]

    def history(self, name: str) -> tuple[SkillArtifact, ...]:
        versions = self._history.get(name, {})
        return tuple(versions[v] for v in sorted(versions, key=_version_key))

    def execute(self, name: str, value: int) -> int:
        artifact = self.current(name)
        return ProgramRegistry([artifact.program]).execute(artifact.program.name, int(value))

    def record_feedback(self, name: str, success: bool) -> SkillArtifact:
        artifact = self.current(name)
        updated = replace(
            artifact,
            successes=artifact.successes + int(bool(success)),
            failures=artifact.failures + int(not bool(success)),
        )
        self._history[name][artifact.version] = updated
        return updated

    def rollback(self, name: str) -> SkillArtifact:
        current = self.current(name)
        prior = [a for a in self.history(name) if a.validated and _version_key(a.version) < _version_key(current.version)]
        if not prior:
            raise RuntimeError('no prior validated skill version')
        restored = prior[-1]
        self._current[name] = restored.version
        return restored

    def select_version(self, name: str, version: str) -> SkillArtifact:
        artifact = self._history.get(name, {}).get(str(version))
        if artifact is None or not artifact.validated:
            raise KeyError((name, version))
        self._current[name] = artifact.version
        return artifact

    def snapshot(self) -> dict:
        skills = {}
        for name in sorted(self._history):
            rows = []
            for artifact in self.history(name):
                rows.append({
                    'name': artifact.name,
                    'version': artifact.version,
                    'demonstrations': [list(x) for x in artifact.demonstrations],
                    'provenance_sha256': artifact.provenance_sha256,
                    'source_uri': artifact.source_uri,
                    'validation_score': artifact.validation_score,
                    'successes': artifact.successes,
                    'failures': artifact.failures,
                    'validated': artifact.validated,
                    'instructions': [(i.op, i.arg) for i in artifact.program.instructions],
                })
            skills[name] = rows
        return {'current': {name: self._current[name] for name in sorted(self._current)}, 'skills': skills}
