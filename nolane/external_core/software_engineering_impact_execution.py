from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.software_engineering_impact import EngineeringTestSelectionProof


COMPONENT_ID = "external.software_engineering.impact_execution"
COMPONENT_VERSION = "0.5.0"
CANONICAL_WRITE_AUTHORITY = False


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


def _refs(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(sorted({_text(value, field="reference") for value in values}))


@dataclass(frozen=True, slots=True)
class EngineeringTestExecutionReceipt:
    execution_id: str
    selection_id: str
    selection_digest: str
    source_revision: str
    environment_digest: str
    required_tests: tuple[str, ...]
    executed_tests: tuple[str, ...]
    missing_tests: tuple[str, ...]
    failed_tests: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    passed: bool
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.execution_id, "test execution id"),
            (self.selection_id, "test selection id"),
            (self.selection_digest, "test selection digest"),
            (self.source_revision, "source revision"),
            (self.environment_digest, "environment digest"),
            (self.digest, "test execution digest"),
        ):
            _text(value, field=field)
        if self.authority != "evidence_only":
            raise ValueError("test execution receipt authority must be evidence_only")
        if not self.required_tests:
            raise ValueError("test execution receipt requires selected tests")
        if not self.evidence_refs:
            raise ValueError("test execution receipt requires execution evidence refs")
        required = set(self.required_tests)
        executed = set(self.executed_tests)
        missing = set(self.missing_tests)
        failed = set(self.failed_tests)
        if missing != required - executed:
            raise ValueError("test execution missing_tests contradict required/executed tests")
        if not failed.issubset(executed):
            raise ValueError("failed test must have been executed")
        if self.passed != (not missing and not failed):
            raise ValueError("test execution pass state contradicts missing/failed tests")

    def payload(self) -> dict[str, Any]:
        return {
            "selection_id": self.selection_id,
            "selection_digest": self.selection_digest,
            "source_revision": self.source_revision,
            "environment_digest": self.environment_digest,
            "required_tests": list(self.required_tests),
            "executed_tests": list(self.executed_tests),
            "missing_tests": list(self.missing_tests),
            "failed_tests": list(self.failed_tests),
            "evidence_refs": list(self.evidence_refs),
            "passed": self.passed,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"execution_id": self.execution_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringTestExecutionReceipt":
        row = cls(
            execution_id=_text(state["execution_id"], field="test execution id"),
            selection_id=_text(state["selection_id"], field="test selection id"),
            selection_digest=_text(state["selection_digest"], field="test selection digest"),
            source_revision=_text(state["source_revision"], field="source revision"),
            environment_digest=_text(state["environment_digest"], field="environment digest"),
            required_tests=_refs(tuple(state.get("required_tests", ()))),
            executed_tests=_refs(tuple(state.get("executed_tests", ()))),
            missing_tests=_refs(tuple(state.get("missing_tests", ()))),
            failed_tests=_refs(tuple(state.get("failed_tests", ()))),
            evidence_refs=_refs(tuple(state.get("evidence_refs", ()))),
            passed=bool(state["passed"]),
            authority=_text(state["authority"], field="test execution authority"),
            digest=_text(state["digest"], field="test execution digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.execution_id != f"eng-test-execution-{expected[:20]}":
            raise ValueError("engineering test execution digest/id mismatch")
        return row


class EngineeringTestExecutionLedger:
    def __init__(self) -> None:
        self._rows: dict[str, EngineeringTestExecutionReceipt] = {}

    def receipts(self) -> tuple[EngineeringTestExecutionReceipt, ...]:
        return tuple(self._rows[key] for key in sorted(self._rows))

    def get(self, execution_id: str) -> EngineeringTestExecutionReceipt:
        try:
            return self._rows[str(execution_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering test execution: {execution_id}") from exc

    def record(
        self,
        *,
        selection: EngineeringTestSelectionProof,
        source_revision: str,
        environment_digest: str,
        executed_tests: tuple[str, ...],
        failed_tests: tuple[str, ...],
        evidence_refs: tuple[str, ...],
    ) -> EngineeringTestExecutionReceipt:
        source = _text(source_revision, field="source revision")
        if source != selection.source_revision:
            raise ValueError("test execution source revision does not match selection source revision")
        if not selection.complete:
            raise ValueError("cannot execute an incomplete differential test selection as sufficient proof")
        required = _refs(selection.selected_tests)
        executed = _refs(executed_tests)
        failed = _refs(failed_tests)
        if not set(failed).issubset(set(executed)):
            raise ValueError("failed test must have been executed")
        missing = tuple(sorted(set(required) - set(executed)))
        refs = _refs(evidence_refs)
        if not refs:
            raise ValueError("test execution requires evidence refs")
        passed = not missing and not failed
        payload = {
            "selection_id": selection.selection_id,
            "selection_digest": selection.digest,
            "source_revision": source,
            "environment_digest": _text(environment_digest, field="environment digest"),
            "required_tests": list(required),
            "executed_tests": list(executed),
            "missing_tests": list(missing),
            "failed_tests": list(failed),
            "evidence_refs": list(refs),
            "passed": passed,
            "authority": "evidence_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringTestExecutionReceipt(
            execution_id=f"eng-test-execution-{digest[:20]}",
            selection_id=selection.selection_id,
            selection_digest=selection.digest,
            source_revision=source,
            environment_digest=payload["environment_digest"],
            required_tests=required,
            executed_tests=executed,
            missing_tests=missing,
            failed_tests=failed,
            evidence_refs=refs,
            passed=passed,
            authority="evidence_only",
            digest=digest,
        )
        existing = self._rows.get(row.execution_id)
        if existing is not None and existing != row:
            raise ValueError("engineering test execution id cannot be rebound")
        self._rows[row.execution_id] = row
        return existing or row

    def to_state(self) -> dict[str, Any]:
        return {"executions": [row.to_state() for row in self.receipts()]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringTestExecutionLedger":
        ledger = cls()
        for value in state.get("executions", ()):
            row = EngineeringTestExecutionReceipt.from_state(value)
            existing = ledger._rows.get(row.execution_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound engineering test execution")
            ledger._rows[row.execution_id] = row
        return ledger


__all__ = (
    "EngineeringTestExecutionReceipt",
    "EngineeringTestExecutionLedger",
)
