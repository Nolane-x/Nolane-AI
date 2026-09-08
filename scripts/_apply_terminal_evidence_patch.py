from __future__ import annotations

from pathlib import Path


EXECUTION = Path("nolane/external_core/execution.py")
VERSIONS = Path("nolane/metadata/component_versions.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


text = EXECUTION.read_text(encoding="utf-8")

text = replace_once(
    text,
    "from nolane.core.canonical_digest import canonical_digest\n",
    "from nolane.core.canonical_digest import canonical_digest, canonical_json\n",
    "canonical imports",
)
text = replace_once(
    text,
    'COMPONENT_VERSION = "0.0.14"\n',
    'COMPONENT_VERSION = "0.0.15"\n',
    "component version",
)
text = replace_once(
    text,
    "    external_core_registry_digest: str | None = None\n"
    "    workspace_epoch_id: str | None = None\n",
    "    external_core_registry_digest: str | None = None\n"
    "    workspace_epoch_id: str | None = None\n"
    "    terminal_evidence_artifact_id: str | None = None\n"
    "    terminal_evidence_digest: str | None = None\n",
    "terminal evidence fields",
)
text = replace_once(
    text,
    '        values = {\n'
    '            "initial_workspace_digest": self.initial_workspace_digest,\n'
    '            "current_workspace_digest": self.current_workspace_digest,\n'
    '            "external_core_registry_digest": self.external_core_registry_digest,\n'
    '            "workspace_epoch_id": self.workspace_epoch_id,\n'
    '        }\n'
    '        normalized = {\n'
    '            key: None if value is None else str(value).strip()\n'
    '            for key, value in values.items()\n'
    '        }\n'
    '        if version == 1:\n'
    '            if any(normalized.values()):\n'
    '                raise ValueError("legacy execution terminal cannot carry modern proof")\n'
    '            for key in normalized:\n'
    '                object.__setattr__(self, key, None)\n'
    '            return\n'
    '        if any(not value for value in normalized.values()):\n'
    '            raise ValueError("execution terminal proof v2 requires complete session proof")\n'
    '        for key, value in normalized.items():\n'
    '            object.__setattr__(self, key, value)\n',
    '        session_values = {\n'
    '            "initial_workspace_digest": self.initial_workspace_digest,\n'
    '            "current_workspace_digest": self.current_workspace_digest,\n'
    '            "external_core_registry_digest": self.external_core_registry_digest,\n'
    '            "workspace_epoch_id": self.workspace_epoch_id,\n'
    '        }\n'
    '        evidence_values = {\n'
    '            "terminal_evidence_artifact_id": self.terminal_evidence_artifact_id,\n'
    '            "terminal_evidence_digest": self.terminal_evidence_digest,\n'
    '        }\n'
    '        values = {**session_values, **evidence_values}\n'
    '        normalized = {\n'
    '            key: None if value is None else str(value).strip()\n'
    '            for key, value in values.items()\n'
    '        }\n'
    '        if version == 1:\n'
    '            if any(normalized.values()):\n'
    '                raise ValueError("legacy execution terminal cannot carry modern proof")\n'
    '            for key in normalized:\n'
    '                object.__setattr__(self, key, None)\n'
    '            return\n'
    '        if any(not normalized[key] for key in session_values):\n'
    '            raise ValueError("execution terminal proof v2 requires complete session proof")\n'
    '        if any(not normalized[key] for key in evidence_values):\n'
    '            raise ValueError("execution terminal evidence proof v2 requires complete binding")\n'
    '        for key, value in normalized.items():\n'
    '            object.__setattr__(self, key, value)\n',
    "terminal proof normalization",
)
text = replace_once(
    text,
    '                    "external_core_registry_digest": self.external_core_registry_digest,\n'
    '                    "workspace_epoch_id": self.workspace_epoch_id,\n',
    '                    "external_core_registry_digest": self.external_core_registry_digest,\n'
    '                    "workspace_epoch_id": self.workspace_epoch_id,\n'
    '                    "terminal_evidence_artifact_id": self.terminal_evidence_artifact_id,\n'
    '                    "terminal_evidence_digest": self.terminal_evidence_digest,\n',
    "terminal payload evidence binding",
)
text = replace_once(
    text,
    '            workspace_epoch_id=(\n'
    '                None if state.get("workspace_epoch_id") is None\n'
    '                else str(state["workspace_epoch_id"])\n'
    '            ),\n'
    '        )\n',
    '            workspace_epoch_id=(\n'
    '                None if state.get("workspace_epoch_id") is None\n'
    '                else str(state["workspace_epoch_id"])\n'
    '            ),\n'
    '            terminal_evidence_artifact_id=(\n'
    '                None if state.get("terminal_evidence_artifact_id") is None\n'
    '                else str(state["terminal_evidence_artifact_id"])\n'
    '            ),\n'
    '            terminal_evidence_digest=(\n'
    '                None if state.get("terminal_evidence_digest") is None\n'
    '                else str(state["terminal_evidence_digest"])\n'
    '            ),\n'
    '        )\n',
    "terminal from_state evidence fields",
)
text = replace_once(
    text,
    '    def bind_session_proof(\n'
    '        cls,\n'
    '        legacy: _BaseExecutionTerminalReceipt,\n'
    '        session: ExecutionSession,\n'
    '    ) -> "ExecutionTerminalReceipt":\n',
    '    def bind_session_proof(\n'
    '        cls,\n'
    '        legacy: _BaseExecutionTerminalReceipt,\n'
    '        session: ExecutionSession,\n'
    '        *,\n'
    '        terminal_evidence_artifact_id: str,\n'
    '        terminal_evidence_digest: str,\n'
    '    ) -> "ExecutionTerminalReceipt":\n',
    "bind_session_proof signature",
)
text = replace_once(
    text,
    '            external_core_registry_digest=session.external_core_registry_digest,\n'
    '            workspace_epoch_id=session.workspace_epoch_id,\n'
    '        )\n',
    '            external_core_registry_digest=session.external_core_registry_digest,\n'
    '            workspace_epoch_id=session.workspace_epoch_id,\n'
    '            terminal_evidence_artifact_id=terminal_evidence_artifact_id,\n'
    '            terminal_evidence_digest=terminal_evidence_digest,\n'
    '        )\n',
    "bind_session_proof evidence values",
)

terminal_marker = '''    def _terminal(\n        self,\n        session: ExecutionSession,\n        state: ExecutionState,\n        reason: str,\n        *,\n        complete_task: bool = False,\n    ) -> _BaseExecutionTerminalReceipt:\n'''
terminal_helpers = '''    @staticmethod\n    def _terminal_evidence_summary(terminal: _BaseExecutionTerminalReceipt) -> dict[str, Any]:\n        return {\n            "session_id": terminal.session_id,\n            "agent_id": terminal.agent_id,\n            "task_id": terminal.task_id,\n            "state": terminal.state.value,\n            "reason": terminal.termination_reason,\n            "counters": {\n                "steps": terminal.steps,\n                "tool_calls": terminal.tool_calls,\n                "external_core_calls": terminal.external_core_calls,\n                "compute_units": terminal.compute_units,\n            },\n            "decision_receipt_ids": list(terminal.decision_receipt_ids),\n            "step_receipt_ids": list(terminal.step_receipt_ids),\n            "core_receipt_ids": list(terminal.core_receipt_ids),\n        }\n\n    def _attest_terminal_evidence(\n        self,\n        terminal: _BaseExecutionTerminalReceipt,\n        artifact_id: str,\n        *,\n        expected_digest: str | None = None,\n    ):\n        try:\n            evidence = self.artifacts.get(artifact_id)\n        except KeyError as exc:\n            raise ValueError("execution terminal evidence artifact is unavailable") from exc\n\n        try:\n            metadata = evidence.metadata\n        except Exception as exc:\n            raise ValueError("execution terminal evidence metadata is invalid") from exc\n        artifact_payload = {\n            "kind": evidence.kind,\n            "producer_agent_id": evidence.producer_agent_id,\n            "content": evidence.content,\n            "evidence_refs": sorted({str(x) for x in evidence.evidence_refs}),\n            "metadata": metadata,\n        }\n        canonical_artifact_digest = canonical_digest(artifact_payload)\n        if (\n            evidence.digest != canonical_artifact_digest\n            or evidence.artifact_id != "artifact-" + canonical_artifact_digest[:24]\n            or evidence.metadata_json != canonical_json(metadata)\n        ):\n            raise ValueError("execution terminal evidence artifact digest/id mismatch")\n        if expected_digest is not None and evidence.digest != str(expected_digest):\n            raise ValueError("execution terminal evidence digest binding mismatch")\n        if evidence.kind != "execution-terminal-evidence":\n            raise ValueError("execution terminal evidence kind mismatch")\n        if evidence.producer_agent_id != terminal.agent_id:\n            raise ValueError("execution terminal evidence producer binding mismatch")\n        if evidence.content != canonical_json(self._terminal_evidence_summary(terminal)):\n            raise ValueError("execution terminal evidence semantic binding mismatch")\n        if metadata != {"task_id": terminal.task_id, "state": terminal.state.value}:\n            raise ValueError("execution terminal evidence metadata binding mismatch")\n        expected_refs = tuple(\n            sorted(\n                {\n                    str(output_id)\n                    for output_id in terminal.output_artifact_ids\n                    if str(output_id) != evidence.artifact_id\n                }\n            )\n        )\n        if evidence.evidence_refs != expected_refs:\n            raise ValueError("execution terminal evidence history binding mismatch")\n        return evidence\n\n'''
text = replace_once(
    text,
    terminal_marker,
    terminal_helpers + terminal_marker,
    "terminal evidence helpers",
)
text = replace_once(
    text,
    '        if session.execution_proof_version < 2:\n'
    '            return legacy\n'
    '        terminal = ExecutionTerminalReceipt.bind_session_proof(legacy, session)\n',
    '        if session.execution_proof_version < 2:\n'
    '            return legacy\n'
    '        evidence_ids = tuple(\n'
    '            artifact_id\n'
    '            for artifact_id in legacy.output_artifact_ids\n'
    '            if artifact_id not in session.output_artifact_ids\n'
    '        )\n'
    '        if len(evidence_ids) != 1:\n'
    '            raise ValueError("execution terminal evidence identity is not unique")\n'
    '        evidence = self._attest_terminal_evidence(legacy, evidence_ids[0])\n'
    '        terminal = ExecutionTerminalReceipt.bind_session_proof(\n'
    '            legacy,\n'
    '            session,\n'
    '            terminal_evidence_artifact_id=evidence.artifact_id,\n'
    '            terminal_evidence_digest=evidence.digest,\n'
    '        )\n',
    "terminal evidence production binding",
)
text = replace_once(
    text,
    '                    expected_terminal_proof = {\n'
    '                        "initial_workspace_digest": session.initial_workspace_digest,\n'
    '                        "current_workspace_digest": session.current_workspace_digest,\n'
    '                        "external_core_registry_digest": session.external_core_registry_digest,\n'
    '                        "workspace_epoch_id": session.workspace_epoch_id,\n'
    '                    }\n',
    '                    expected_terminal_proof = {\n'
    '                        "initial_workspace_digest": session.initial_workspace_digest,\n'
    '                        "current_workspace_digest": session.current_workspace_digest,\n'
    '                        "external_core_registry_digest": session.external_core_registry_digest,\n'
    '                        "workspace_epoch_id": session.workspace_epoch_id,\n'
    '                    }\n',
    "terminal proof anchor",
)
validation_anchor = '''                    if mismatches:\n                        raise ValueError(\n                            "execution terminal proof binding mismatch: "\n                            + ", ".join(mismatches)\n                        )\n'''
validation_new = validation_anchor + '''                    evidence_artifact_id = str(\n                        getattr(terminal, "terminal_evidence_artifact_id", "") or ""\n                    ).strip()\n                    evidence_digest = str(\n                        getattr(terminal, "terminal_evidence_digest", "") or ""\n                    ).strip()\n                    if not evidence_artifact_id or not evidence_digest:\n                        raise ValueError(\n                            "execution terminal evidence proof v2 requires complete binding"\n                        )\n                    if evidence_artifact_id not in terminal.output_artifact_ids:\n                        raise ValueError(\n                            "execution terminal evidence output binding mismatch"\n                        )\n                    self._attest_terminal_evidence(\n                        terminal,\n                        evidence_artifact_id,\n                        expected_digest=evidence_digest,\n                    )\n'''
text = replace_once(
    text,
    validation_anchor,
    validation_new,
    "terminal evidence restore validation",
)

EXECUTION.write_text(text, encoding="utf-8")

versions = VERSIONS.read_text(encoding="utf-8")
versions = replace_once(
    versions,
    '        "external.execution.control": 15,\n',
    '        "external.execution.control": 16,\n',
    "canonical execution revision",
)
VERSIONS.write_text(versions, encoding="utf-8")
