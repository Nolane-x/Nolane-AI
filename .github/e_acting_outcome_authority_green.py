from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one anchor, found {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Acting protocol: persist a backward-compatible optional digest that commits the
# exact core receipt authority payload observed during forward execution.
replace_once(
    "nolane/external_core/acting_protocol.py",
    'COMPONENT_VERSION = "0.1.5"',
    'COMPONENT_VERSION = "0.1.6"',
)
replace_once(
    "nolane/external_core/acting_protocol.py",
    '    outcome_ref: str = ""\n    outcome_success: bool | None = None\n    postcondition_evidence_refs: tuple[str, ...] = ()\n',
    '    outcome_ref: str = ""\n    outcome_success: bool | None = None\n    outcome_digest: str = ""\n    postcondition_evidence_refs: tuple[str, ...] = ()\n',
)
replace_once(
    "nolane/external_core/acting_protocol.py",
    '    def _state_payload(self) -> dict[str, Any]:\n        return {\n',
    '    def _state_payload(self) -> dict[str, Any]:\n        payload = {\n',
)
replace_once(
    "nolane/external_core/acting_protocol.py",
    '            "event_receipt_ids": list(self.event_receipt_ids),\n        }\n\n    @property\n    def digest(self) -> str:\n',
    '            "event_receipt_ids": list(self.event_receipt_ids),\n        }\n        if self.outcome_digest:\n            payload["outcome_digest"] = self.outcome_digest\n        return payload\n\n    @property\n    def digest(self) -> str:\n',
)
replace_once(
    "nolane/external_core/acting_protocol.py",
    '            outcome_ref=str(state.get("outcome_ref", "")),\n            outcome_success=state.get("outcome_success"),\n            postcondition_evidence_refs=tuple(str(x) for x in state.get("postcondition_evidence_refs", ())),\n',
    '            outcome_ref=str(state.get("outcome_ref", "")),\n            outcome_success=state.get("outcome_success"),\n            outcome_digest=str(state.get("outcome_digest", "")),\n            postcondition_evidence_refs=tuple(str(x) for x in state.get("postcondition_evidence_refs", ())),\n',
)
replace_once(
    "nolane/external_core/acting_protocol.py",
    '        outcome_ref: str,\n        success: bool,\n        now_ms: int,\n',
    '        outcome_ref: str,\n        success: bool,\n        outcome_digest: str = "",\n        now_ms: int,\n',
)
replace_once(
    "nolane/external_core/acting_protocol.py",
    '        ref = str(outcome_ref).strip()\n        if not ref:\n            raise ValueError("outcome reference is required")\n        return self._append_event(\n            row,\n            phase=ActionPhase.OUTCOME_OBSERVED,\n            event_type="outcome_observed",\n            evidence_refs=(ref,),\n            payload={"success": bool(success)},\n            outcome_ref=ref,\n            outcome_success=bool(success),\n        )\n',
    '        ref = str(outcome_ref).strip()\n        if not ref:\n            raise ValueError("outcome reference is required")\n        authority_digest = str(outcome_digest).strip()\n        payload: dict[str, Any] = {"success": bool(success)}\n        if authority_digest:\n            payload["outcome_digest"] = authority_digest\n        return self._append_event(\n            row,\n            phase=ActionPhase.OUTCOME_OBSERVED,\n            event_type="outcome_observed",\n            evidence_refs=(ref,),\n            payload=payload,\n            outcome_ref=ref,\n            outcome_success=bool(success),\n            outcome_digest=authority_digest,\n        )\n',
)
replace_once(
    "nolane/external_core/acting_protocol.py",
    '        if outcome is None:\n            if row.outcome_ref or row.outcome_success is not None:\n                raise ValueError("action record outcome disagrees with lifecycle events")\n        else:\n            if row.outcome_success is None or outcome.evidence_refs != (row.outcome_ref,):\n                raise ValueError("action record outcome disagrees with lifecycle event")\n            expected_payload = canonical_digest({"success": bool(row.outcome_success)})\n            if outcome.payload_digest != expected_payload:\n                raise ValueError("action record outcome result disagrees with lifecycle event")\n',
    '        if outcome is None:\n            if row.outcome_ref or row.outcome_success is not None or row.outcome_digest:\n                raise ValueError("action record outcome disagrees with lifecycle events")\n        else:\n            if row.outcome_success is None or outcome.evidence_refs != (row.outcome_ref,):\n                raise ValueError("action record outcome disagrees with lifecycle event")\n            outcome_payload: dict[str, Any] = {"success": bool(row.outcome_success)}\n            if row.outcome_digest:\n                outcome_payload["outcome_digest"] = row.outcome_digest\n            expected_payload = canonical_digest(outcome_payload)\n            if outcome.payload_digest != expected_payload:\n                raise ValueError("action record outcome result disagrees with lifecycle event")\n',
)
replace_once(
    "nolane/external_core/acting_protocol.py",
    '        if not ref:\n            raise ValueError("commit reference is required")\n        return self._append_event(\n            row,\n            phase=ActionPhase.COMMITTED,\n            event_type="committed",\n            evidence_refs=(ref,),\n            payload={"outcome_ref": row.outcome_ref},\n            commit_ref=ref,\n        )\n',
    '        if not ref:\n            raise ValueError("commit reference is required")\n        payload: dict[str, Any] = {"outcome_ref": row.outcome_ref}\n        if row.outcome_digest:\n            payload["outcome_digest"] = row.outcome_digest\n        return self._append_event(\n            row,\n            phase=ActionPhase.COMMITTED,\n            event_type="committed",\n            evidence_refs=(ref,),\n            payload=payload,\n            commit_ref=ref,\n        )\n',
)
replace_once(
    "nolane/external_core/acting_protocol.py",
    '            if committed.evidence_refs != (row.commit_ref,):\n                raise ValueError("action record commit reference disagrees with lifecycle event")\n            if committed.payload_digest != canonical_digest({"outcome_ref": row.outcome_ref}):\n                raise ValueError("action record commit outcome disagrees with lifecycle event")\n',
    '            if committed.evidence_refs != (row.commit_ref,):\n                raise ValueError("action record commit reference disagrees with lifecycle event")\n            commit_payload: dict[str, Any] = {"outcome_ref": row.outcome_ref}\n            if row.outcome_digest:\n                commit_payload["outcome_digest"] = row.outcome_digest\n            if committed.payload_digest != canonical_digest(commit_payload):\n                raise ValueError("action record commit outcome disagrees with lifecycle event")\n',
)

# Acting runtime: canonicalize the authority-relevant receipt projection and pin
# it into the protocol before any postcondition/commit transition.
replace_once(
    "nolane/external_core/acting_runtime.py",
    'COMPONENT_VERSION = "0.1.6"',
    'COMPONENT_VERSION = "0.1.7"',
)
replace_once(
    "nolane/external_core/acting_runtime.py",
    '    @staticmethod\n    def _validate_core_receipt(\n',
    '''    @staticmethod\n    def _core_receipt_authority_digest(receipt: CoreReceipt) -> str:\n        return canonical_digest(\n            {\n                "receipt_id": str(receipt.receipt_id),\n                "agent_id": str(receipt.agent_id),\n                "task_id": str(receipt.task_id),\n                "tool_id": str(receipt.tool_id),\n                "operation": str(receipt.operation),\n                "input_digest": str(receipt.input_digest),\n                "authorized": bool(receipt.authorized),\n                "success": bool(receipt.success),\n                "failure_kind": (\n                    None if receipt.failure_kind is None else str(receipt.failure_kind)\n                ),\n                "before_workspace_digest": str(receipt.before_workspace_digest),\n                "after_workspace_digest": str(receipt.after_workspace_digest),\n                "output_artifact_ids": [str(x) for x in receipt.output_artifact_ids],\n                "evidence_artifact_id": str(receipt.evidence_artifact_id),\n                "core_contract_digest": str(getattr(receipt, "core_contract_digest", "")),\n                "workspace_epoch_id": str(getattr(receipt, "workspace_epoch_id", "")),\n            }\n        )\n\n    @staticmethod\n    def _validate_core_receipt(\n''',
)
replace_once(
    "nolane/external_core/acting_runtime.py",
    '        workspace_epoch_id: str,\n    ) -> None:\n        expected = {\n',
    '        workspace_epoch_id: str,\n        outcome_digest: str,\n    ) -> None:\n        expected = {\n',
)
replace_once(
    "nolane/external_core/acting_runtime.py",
    '        if getattr(receipt, "success", None) is not True:\n            mismatches.append("success")\n        if mismatches:\n',
    '        if getattr(receipt, "success", None) is not True:\n            mismatches.append("success")\n        expected_outcome_digest = str(outcome_digest).strip()\n        if (\n            not expected_outcome_digest\n            or TransactionalExternalCoreExecutor._core_receipt_authority_digest(receipt)\n            != expected_outcome_digest\n        ):\n            mismatches.append("outcome_digest")\n        if mismatches:\n',
)
replace_once(
    "nolane/external_core/acting_runtime.py",
    '            core_contract_digest=str(core_contract_digest),\n            workspace_epoch_id=str(workspace_epoch_id),\n        )\n',
    '            core_contract_digest=str(core_contract_digest),\n            workspace_epoch_id=str(workspace_epoch_id),\n            outcome_digest=str(row.outcome_digest),\n        )\n',
)
replace_once(
    "nolane/external_core/acting_runtime.py",
    '                outcome_ref=str(receipt.receipt_id),\n                success=bool(receipt.success),\n                now_ms=current_now_ms(),\n',
    '                outcome_ref=str(receipt.receipt_id),\n                success=bool(receipt.success),\n                outcome_digest=self._core_receipt_authority_digest(receipt),\n                now_ms=current_now_ms(),\n',
)

# Control-plane recovery: modern proof-v2 projection requires the exact forward
# receipt digest pinned by the Acting ledger; legacy rows validate it when present.
replace_once(
    "nolane/external_core/execution.py",
    'COMPONENT_VERSION = "0.0.10"',
    'COMPONENT_VERSION = "0.0.11"',
)
replace_once(
    "nolane/external_core/execution.py",
    "        if getattr(core, 'success', None) is not True:\n            mismatches.append('success')\n\n        if session.execution_proof_version >= 2:\n",
    "        if getattr(core, 'success', None) is not True:\n            mismatches.append('success')\n\n        recorded_outcome_digest = str(getattr(row, 'outcome_digest', '')).strip()\n        if session.execution_proof_version >= 2 and not recorded_outcome_digest:\n            mismatches.append('outcome_digest')\n        elif (\n            recorded_outcome_digest\n            and self.acting_executor._core_receipt_authority_digest(core)\n            != recorded_outcome_digest\n        ):\n            mismatches.append('outcome_digest')\n\n        if session.execution_proof_version >= 2:\n",
)
replace_once(
    "nolane/metadata/component_versions.py",
    '        "external.execution.control": 10,',
    '        "external.execution.control": 11,',
)
for old, new in (
    ('assert canonical.COMPONENT_VERSION == "0.0.10"', 'assert canonical.COMPONENT_VERSION == "0.0.11"'),
    ('assert row.component_version == "0.0.10"', 'assert row.component_version == "0.0.11"'),
    ('assert str(component_version("external.execution.control")) == "0.0.10"', 'assert str(component_version("external.execution.control")) == "0.0.11"'),
):
    replace_once("tests/test_refoundation_wave5aa_native_execution_control.py", old, new)

# Make the recovery regression a modern proof-v2 case and seed the ledger with
# the exact forward receipt digest before hostile receipt substitution.
replace_once(
    "tests/test_refoundation_acting_recovery_projection_authority.py",
    '    before_workspace_digest: str = "workspace-before"\n    after_workspace_digest: str = "workspace-after"\n',
    '    before_workspace_digest: str = "workspace-before"\n    after_workspace_digest: str = "workspace-after"\n    core_contract_digest: str = ""\n    workspace_epoch_id: str = "epoch-v1"\n',
)
replace_once(
    "tests/test_refoundation_acting_recovery_projection_authority.py",
    'class _NeverUse:\n',
    'class _ExternalCores:\n    contract_digest = "registry-v1"\n\n    def get(self, _core_id: str):\n        raise AssertionError("built-in recovery test must not resolve external core contracts")\n\n\nclass _NeverUse:\n',
)
replace_once(
    "tests/test_refoundation_acting_recovery_projection_authority.py",
    '        current_workspace_digest="workspace-before",\n        decision_receipt_ids=("decision-1",),\n',
    '        current_workspace_digest="workspace-before",\n        execution_proof_version=2,\n        external_core_registry_digest="registry-v1",\n        workspace_epoch_id="epoch-v1",\n        decision_receipt_ids=("decision-1",),\n',
)
replace_once(
    "tests/test_refoundation_acting_recovery_projection_authority.py",
    '        budget=ActionBudget(max_attempts=1, max_local_mutations=1, max_external_effects=0),\n    )\n',
    '        budget=ActionBudget(max_attempts=1, max_local_mutations=1, max_external_effects=0),\n        core_contract_digest="",\n        workspace_epoch_id="epoch-v1",\n    )\n',
)
replace_once(
    "tests/test_refoundation_acting_recovery_projection_authority.py",
    '    protocol.observe_outcome(contract.action_id, outcome_ref="core-1", success=True, now_ms=103)\n',
    '    protocol.observe_outcome(\n        contract.action_id,\n        outcome_ref="core-1",\n        success=True,\n        outcome_digest=TransactionalExternalCoreExecutor._core_receipt_authority_digest(_CoreReceipt()),\n        now_ms=103,\n    )\n',
)
replace_once(
    "tests/test_refoundation_acting_recovery_projection_authority.py",
    '        external_cores=_NeverUse(),\n',
    '        external_cores=_ExternalCores(),\n',
)

# Replay must not export substituted output authority either.
replace_once(
    "tests/test_refoundation_acting_replay_authority.py",
    '\ndef test_noncommitted_terminal_replay_never_exports_core_outputs(tmp_path: Path) -> None:\n',
    '''\ndef test_committed_replay_rejects_substituted_output_payload(tmp_path: Path) -> None:\n    workspace = _workspace(tmp_path)\n    raw = _Executor()\n    kernel = TransactionalExternalCoreExecutor(executor=raw)\n    try:\n        first = _invoke(kernel, workspace)\n        original = raw.get_receipt(first.core_receipt_id)\n        raw._receipts[first.core_receipt_id] = replace(\n            original, output_artifact_ids=("artifact-poisoned",)\n        )\n\n        with pytest.raises(ValueError, match="replay core receipt provenance mismatch"):\n            _invoke(kernel, workspace)\n        assert raw.calls == 1\n    finally:\n        workspace.close()\n\n\ndef test_noncommitted_terminal_replay_never_exports_core_outputs(tmp_path: Path) -> None:\n''',
)

print("E Acting outcome authority digest patch applied")
