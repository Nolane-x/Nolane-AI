from __future__ import annotations

import hashlib
import json
from typing import Iterable

from .epistemic_program import EpistemicProgram
from .r22_runtime import R22Runtime
from .skill_memory import SkillArtifact, SkillRegistry
from .skill_synthesis import BoundedSkillSynthesizer, Demonstration


class ContinualSkillLayer(R22Runtime):
    """R2.2-compatible runtime with zero-parameter continual skill synthesis."""

    new_neural_parameters = 0
    effective_neural_parameters = 78_779_253

    def __init__(self, *args, synthesizer: BoundedSkillSynthesizer | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.skill_synthesizer = synthesizer or BoundedSkillSynthesizer()
        self.skills = SkillRegistry()

    @staticmethod
    def _provenance_digest(name: str, version: str, demonstrations: tuple[Demonstration, ...], source_uri: str) -> str:
        payload = {
            'name': str(name),
            'version': str(version),
            'source_uri': str(source_uri),
            'demonstrations': [(int(d.input_value), int(d.output_value)) for d in demonstrations],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def learn_skill(self, name: str, version: str, demonstrations: Iterable[Demonstration], *, source_uri: str) -> SkillArtifact:
        demos = tuple(demonstrations)
        result = self.skill_synthesizer.synthesize(str(name), str(version), demos)
        if not result.resolved or result.program is None:
            raise RuntimeError(f'skill synthesis unresolved: {result.reason}')
        provenance = self._provenance_digest(str(name), str(version), demos, str(source_uri))
        program = EpistemicProgram(
            str(name), result.instructions, (f'skill:{provenance}',), (provenance,), (str(source_uri),), (str(version),),
        )
        artifact = SkillArtifact(
            name=str(name), version=str(version), program=program,
            demonstrations=tuple((int(d.input_value), int(d.output_value)) for d in demos),
            provenance_sha256=provenance, source_uri=str(source_uri), validation_score=1.0,
        )
        return self.skills.install(artifact)

    def apply_skill(self, name: str, value: int) -> int:
        return self.skills.execute(str(name), int(value))

    def apply_composition(self, names: Iterable[str], value: int) -> int:
        current = int(value)
        for name in names:
            current = self.apply_skill(str(name), current)
        return current

    def record_skill_feedback(self, name: str, success: bool) -> SkillArtifact:
        return self.skills.record_feedback(str(name), bool(success))
