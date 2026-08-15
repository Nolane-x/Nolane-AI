from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .epistemic_program import Instruction
from .skill_synthesis import Demonstration, _apply_instruction, _path_key


@dataclass(frozen=True)
class ProgramHypothesis:
    representative: tuple[Instruction, ...]
    signature: tuple[int, ...]


@dataclass(frozen=True)
class SemanticClass:
    signature: tuple[int, ...]
    representative: tuple[Instruction, ...]


@dataclass(frozen=True)
class VersionSpace:
    probe_domain: tuple[int, ...]
    classes: tuple[SemanticClass, ...]
    observations: tuple[tuple[int, int], ...]
    candidates_evaluated: int
    enumeration_complete: bool = True

    def output_for(self, semantic_class: SemanticClass, input_value: int) -> int:
        try:
            index = self.probe_domain.index(int(input_value))
        except ValueError as exc:
            raise ValueError('input outside probe domain') from exc
        return int(semantic_class.signature[index])


@dataclass(frozen=True)
class ActiveIdentificationResult:
    resolved: bool
    reason: str
    representative: tuple[Instruction, ...]
    surviving_classes: int
    oracle_calls: int
    observations: tuple[tuple[int, int], ...]
    signature: tuple[int, ...] | None


class ActiveProgramIdentifier:
    """Zero-parameter bounded program identifier over a finite semantic domain."""

    trainable_parameter_count = 0
    new_neural_parameters = 0

    def __init__(
        self,
        *,
        probe_domain: Iterable[int],
        max_depth: int = 3,
        max_candidates: int = 100_000,
        max_abs_value: int = 10**9,
        add_limit: int = 12,
        mul_limit: int = 5,
        xor_limit: int = 15,
        mod_limit: int = 31,
    ):
        domain = tuple(dict.fromkeys(int(x) for x in probe_domain))
        if len(domain) < 2:
            raise ValueError('probe_domain must contain at least two distinct values')
        if max_depth < 1 or max_candidates < 1:
            raise ValueError('search budgets must be positive')
        self.probe_domain = domain
        self.max_depth = int(max_depth)
        self.max_candidates = int(max_candidates)
        self.max_abs_value = int(max_abs_value)
        self._instructions = self._make_instruction_space(add_limit, mul_limit, xor_limit, mod_limit)

    @staticmethod
    def _make_instruction_space(add_limit: int, mul_limit: int, xor_limit: int, mod_limit: int) -> tuple[Instruction, ...]:
        rows: list[Instruction] = []
        rows.extend(Instruction('ADD', arg) for arg in range(-int(add_limit), int(add_limit) + 1) if arg != 0)
        rows.extend(Instruction('MUL', arg) for arg in range(-int(mul_limit), int(mul_limit) + 1) if arg not in (0, 1))
        rows.extend(Instruction('XOR', arg) for arg in range(1, int(xor_limit) + 1))
        rows.extend(Instruction('MOD', arg) for arg in range(2, int(mod_limit) + 1))
        return tuple(rows)

    def _normalize_demonstrations(self, demonstrations: Iterable[Demonstration]) -> tuple[Demonstration, ...]:
        by_input: dict[int, int] = {}
        domain = set(self.probe_domain)
        for demo in demonstrations:
            x, y = int(demo.input_value), int(demo.output_value)
            if x not in domain:
                raise ValueError('demonstration input outside probe domain')
            if x in by_input and by_input[x] != y:
                raise ValueError('conflicting demonstrations for the same input')
            by_input[x] = y
        if not by_input:
            raise ValueError('at least one demonstration is required')
        return tuple(Demonstration(x, by_input[x]) for x in sorted(by_input))

    def _enumerate_semantics(self) -> tuple[dict[tuple[int, ...], tuple[Instruction, ...]], int, bool]:
        identity = tuple(self.probe_domain)
        seen: dict[tuple[int, ...], tuple[Instruction, ...]] = {identity: ()}
        frontier: dict[tuple[int, ...], tuple[Instruction, ...]] = {identity: ()}
        candidates_evaluated = 0
        for _depth in range(1, self.max_depth + 1):
            next_frontier: dict[tuple[int, ...], tuple[Instruction, ...]] = {}
            for signature, path in sorted(frontier.items(), key=lambda item: (_path_key(item[1]), item[0])):
                for instruction in self._instructions:
                    candidates_evaluated += 1
                    if candidates_evaluated > self.max_candidates:
                        seen.pop(identity, None)
                        return seen, candidates_evaluated - 1, False
                    try:
                        out = tuple(_apply_instruction(v, instruction) for v in signature)
                    except (ArithmeticError, ValueError, OverflowError):
                        continue
                    if any(abs(v) > self.max_abs_value for v in out):
                        continue
                    new_path = path + (instruction,)
                    previous = seen.get(out)
                    if previous is None:
                        seen[out] = new_path
                        next_frontier[out] = new_path
                    elif len(previous) == len(new_path) and _path_key(new_path) < _path_key(previous):
                        seen[out] = new_path
                        if out in next_frontier:
                            next_frontier[out] = new_path
            frontier = next_frontier
            if not frontier:
                break
        seen.pop(identity, None)
        return seen, candidates_evaluated, True

    def build_version_space(self, demonstrations: Iterable[Demonstration]) -> VersionSpace:
        demos = self._normalize_demonstrations(demonstrations)
        semantic_paths, candidates_evaluated, enumeration_complete = self._enumerate_semantics()
        index = {value: i for i, value in enumerate(self.probe_domain)}
        classes: list[SemanticClass] = []
        for signature, path in semantic_paths.items():
            if all(signature[index[int(d.input_value)]] == int(d.output_value) for d in demos):
                classes.append(SemanticClass(signature=signature, representative=path))
        classes.sort(key=lambda row: (_path_key(row.representative), row.signature))
        observations = tuple((int(d.input_value), int(d.output_value)) for d in demos)
        return VersionSpace(self.probe_domain, tuple(classes), observations, candidates_evaluated, enumeration_complete)
    @staticmethod
    def select_discriminator(space: VersionSpace) -> int | None:
        if len(space.classes) <= 1:
            return None
        observed = {int(x) for x, _ in space.observations}
        best: tuple[int, int, int] | None = None
        best_input: int | None = None
        for index, input_value in enumerate(space.probe_domain):
            if int(input_value) in observed:
                continue
            partitions: dict[int, int] = {}
            for semantic_class in space.classes:
                output = int(semantic_class.signature[index])
                partitions[output] = partitions.get(output, 0) + 1
            if len(partitions) <= 1:
                continue
            worst = max(partitions.values())
            # Sum of squared partition sizes is proportional to expected remainder
            # under a uniform prior over surviving semantic classes.
            expected_numerator = sum(size * size for size in partitions.values())
            score = (worst, expected_numerator, int(input_value))
            if best is None or score < best:
                best = score
                best_input = int(input_value)
        return best_input

    @staticmethod
    def select_falsification_probe(space: VersionSpace) -> int | None:
        observed = {int(x) for x, _ in space.observations}
        candidates = [int(x) for x in space.probe_domain if int(x) not in observed]
        if not candidates:
            return None
        if not observed:
            return min(candidates)
        def score(x: int) -> tuple[int, int]:
            distance = min(abs(int(x) - int(o)) for o in observed)
            return (-distance, int(x))
        return min(candidates, key=score)

    @staticmethod
    def resolve_space_without_oracle(space: VersionSpace) -> ActiveIdentificationResult:
        if not space.classes:
            return ActiveIdentificationResult(False, 'no_consistent_program', (), 0, 0, space.observations, None)
        if len(space.classes) == 1:
            chosen = space.classes[0]
            return ActiveIdentificationResult(
                True, 'resolved_unique_semantics', chosen.representative, 1, 0, space.observations, chosen.signature
            )
        signatures = {row.signature for row in space.classes}
        if len(signatures) == 1:
            chosen = min(space.classes, key=lambda row: _path_key(row.representative))
            return ActiveIdentificationResult(
                True, 'observationally_equivalent', chosen.representative, len(space.classes), 0,
                space.observations, chosen.signature
            )
        return ActiveIdentificationResult(
            False, 'no_legal_discriminator', (), len(space.classes), 0, space.observations, None
        )

    @staticmethod
    def _filter_space(space: VersionSpace, input_value: int, output_value: int) -> VersionSpace:
        try:
            index = space.probe_domain.index(int(input_value))
        except ValueError as exc:
            raise ValueError('input outside probe domain') from exc
        surviving = tuple(
            row for row in space.classes if int(row.signature[index]) == int(output_value)
        )
        observations = space.observations + ((int(input_value), int(output_value)),)
        return VersionSpace(
            space.probe_domain, surviving, observations, space.candidates_evaluated, space.enumeration_complete
        )

    def identify_from_space(
        self,
        space: VersionSpace,
        oracle: Callable[[int], int],
        *,
        max_oracle_calls: int = 3,
    ) -> ActiveIdentificationResult:
        if max_oracle_calls < 0:
            raise ValueError('max_oracle_calls must be non-negative')
        if tuple(space.probe_domain) != self.probe_domain:
            raise ValueError('version-space probe domain does not match identifier')
        if not space.enumeration_complete:
            return ActiveIdentificationResult(
                False, 'candidate_budget_exhausted', (), len(space.classes), 0, space.observations, None
            )
        if not space.classes:
            return ActiveIdentificationResult(
                False, 'no_consistent_program', (), 0, 0, space.observations, None
            )

        oracle_calls = 0
        if len(space.classes) == 1:
            confirmation = self.select_falsification_probe(space)
            if confirmation is not None:
                if int(max_oracle_calls) == 0:
                    return ActiveIdentificationResult(
                        False, 'confirmation_budget_exhausted', (), 1, 0, space.observations, None
                    )
                observed_output = int(oracle(int(confirmation)))
                oracle_calls = 1
                space = self._filter_space(space, int(confirmation), observed_output)
                if not space.classes:
                    return ActiveIdentificationResult(
                        False, 'no_consistent_program', (), 0, oracle_calls, space.observations, None
                    )

        while len(space.classes) > 1:
            if oracle_calls >= int(max_oracle_calls):
                return ActiveIdentificationResult(
                    False, 'oracle_budget_exhausted', (), len(space.classes), oracle_calls, space.observations, None
                )
            query = self.select_discriminator(space)
            if query is None:
                unresolved = self.resolve_space_without_oracle(space)
                return ActiveIdentificationResult(
                    unresolved.resolved, unresolved.reason, unresolved.representative, unresolved.surviving_classes,
                    oracle_calls, space.observations, unresolved.signature
                )
            observed_output = int(oracle(int(query)))
            oracle_calls += 1
            space = self._filter_space(space, int(query), observed_output)
            if not space.classes:
                return ActiveIdentificationResult(
                    False, 'no_consistent_program', (), 0, oracle_calls, space.observations, None
                )

        chosen = space.classes[0]
        return ActiveIdentificationResult(
            True, 'resolved_unique_semantics', chosen.representative, 1, oracle_calls, space.observations, chosen.signature
        )

    def identify(
        self,
        demonstrations: Iterable[Demonstration],
        oracle: Callable[[int], int],
        *,
        max_oracle_calls: int = 3,
    ) -> ActiveIdentificationResult:
        if max_oracle_calls < 0:
            raise ValueError('max_oracle_calls must be non-negative')
        space = self.build_version_space(demonstrations)
        return self.identify_from_space(space, oracle, max_oracle_calls=max_oracle_calls)
