from __future__ import annotations

from .epistemic_program import ProgramRegistry, compile_program_chunk
from .epistemic_workspace import EpistemicWorkspace
from .r21_runtime import R21Runtime


class R22Runtime(R21Runtime):
    """R2.1-compatible runtime with a version-aware epistemic workspace."""

    new_neural_parameters = 0
    effective_neural_parameters = 78_779_253

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace = EpistemicWorkspace()
        self.programs = ProgramRegistry()
        self._compiled_chunk_ids: set[str] = set()

    def retrieve(self, **kwargs):
        decision = super().retrieve(**kwargs)
        if decision.retrieved:
            self.workspace.ingest_many(decision.chunks)
        return decision

    def belief(self, subject: str, relation: str):
        return self.workspace.belief(subject, relation)

    def missing_queries(self, subject: str, relation: str):
        return self.workspace.missing_queries(subject, relation)

    def compile_retrieved_programs(self) -> tuple[str, ...]:
        compiled = []
        for chunk in self.workspace.chunks():
            if chunk.chunk_id in self._compiled_chunk_ids:
                continue
            if not chunk.text.lstrip().startswith('PROGRAM '):
                continue
            program = compile_program_chunk(chunk)
            self.programs.register(program)
            self._compiled_chunk_ids.add(chunk.chunk_id)
            compiled.append(program.name)
        return tuple(sorted(compiled))

    def execute_program(self, name: str, value: int) -> int:
        return self.programs.execute(name, value)
