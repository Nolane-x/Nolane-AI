from pathlib import Path

path = Path("nolane/external_core/acting_runtime.py")
text = path.read_text(encoding="utf-8")

old_version = 'COMPONENT_VERSION = "0.1.5"'
new_version = 'COMPONENT_VERSION = "0.1.6"'
if old_version in text:
    text = text.replace(old_version, new_version, 1)
elif new_version not in text:
    raise SystemExit("unexpected acting runtime version")

old_replay = '''    def _replay(self, row: ActionRecord) -> ActingInvocationResult:\n        if row.phase not in {\n            ActionPhase.COMMITTED,\n            ActionPhase.ROLLED_BACK,\n            ActionPhase.DEGRADED,\n            ActionPhase.CANCELLED,\n        }:\n            raise ProtocolViolation(\n                "idempotent action is already in progress; explicit resume/recovery is required"\n            )\n        receipt_id = row.outcome_ref\n        outputs: tuple[str, ...] = ()\n        if receipt_id:\n            receipt = self.executor.get_receipt(receipt_id)\n            outputs = tuple(str(x) for x in receipt.output_artifact_ids)\n        return ActingInvocationResult(\n            record=row,\n            core_receipt_id=receipt_id,\n            output_artifact_ids=outputs,\n            replayed=True,\n        )\n'''

new_replay = '''    @staticmethod\n    def _validate_replay_core_receipt(\n        receipt: CoreReceipt,\n        *,\n        receipt_id: str,\n        agent_id: str,\n        task_id: str,\n        action: ToolAction,\n        input_digest: str,\n        workspace_digest: str,\n        core_contract_digest: str,\n        workspace_epoch_id: str,\n    ) -> None:\n        expected = {\n            "receipt_id": str(receipt_id),\n            "agent_id": str(agent_id),\n            "task_id": str(task_id),\n            "tool_id": action.tool_id,\n            "operation": action.operation,\n            "input_digest": str(input_digest),\n            "after_workspace_digest": str(workspace_digest),\n            "core_contract_digest": str(core_contract_digest),\n            "workspace_epoch_id": str(workspace_epoch_id),\n        }\n        mismatches = [\n            field\n            for field, expected_value in expected.items()\n            if getattr(receipt, field, None) != expected_value\n        ]\n        if getattr(receipt, "authorized", None) is not True:\n            mismatches.append("authorized")\n        if getattr(receipt, "success", None) is not True:\n            mismatches.append("success")\n        if mismatches:\n            raise ValueError(\n                "replay core receipt provenance mismatch: "\n                + ", ".join(dict.fromkeys(mismatches))\n            )\n\n    def _replay(\n        self,\n        row: ActionRecord,\n        *,\n        expected_action_id: str,\n        agent_id: str,\n        task_id: str,\n        workspace: RepositoryWorkspace,\n        action: ToolAction,\n        core_contract_digest: str,\n        workspace_epoch_id: str,\n    ) -> ActingInvocationResult:\n        if row.action_id != str(expected_action_id):\n            raise PermissionError("replay action authority mismatch")\n        if row.phase not in {\n            ActionPhase.COMMITTED,\n            ActionPhase.ROLLED_BACK,\n            ActionPhase.DEGRADED,\n            ActionPhase.CANCELLED,\n        }:\n            raise ProtocolViolation(\n                "idempotent action is already in progress; explicit resume/recovery is required"\n            )\n        if row.phase is not ActionPhase.COMMITTED:\n            return ActingInvocationResult(\n                record=row,\n                core_receipt_id="",\n                output_artifact_ids=(),\n                replayed=True,\n            )\n        receipt_id = str(row.outcome_ref).strip()\n        if not receipt_id or row.commit_ref != receipt_id:\n            raise ValueError("replay committed action lacks exact committed receipt authority")\n        receipt = self.executor.get_receipt(receipt_id)\n        self._validate_replay_core_receipt(\n            receipt,\n            receipt_id=receipt_id,\n            agent_id=str(agent_id),\n            task_id=str(task_id),\n            action=action,\n            input_digest=row.contract.input_digest,\n            workspace_digest=workspace.digest,\n            core_contract_digest=str(core_contract_digest),\n            workspace_epoch_id=str(workspace_epoch_id),\n        )\n        return ActingInvocationResult(\n            record=row,\n            core_receipt_id=receipt_id,\n            output_artifact_ids=tuple(str(x) for x in receipt.output_artifact_ids),\n            replayed=True,\n        )\n'''

if old_replay in text:
    text = text.replace(old_replay, new_replay, 1)
elif new_replay not in text:
    raise SystemExit("acting runtime replay block not found")

old_call = '''        row = self.protocol.propose(contract)\n        if row.action_id != action_id or row.phase is not ActionPhase.PROPOSED:\n            return self._replay(row)\n'''
new_call = '''        row = self.protocol.propose(contract)\n        if row.action_id != action_id or row.phase is not ActionPhase.PROPOSED:\n            return self._replay(\n                row,\n                expected_action_id=action_id,\n                agent_id=str(agent_id),\n                task_id=str(task_id),\n                workspace=workspace,\n                action=action,\n                core_contract_digest=core_digest,\n                workspace_epoch_id=epoch_id,\n            )\n'''
if old_call in text:
    text = text.replace(old_call, new_call, 1)
elif new_call not in text:
    raise SystemExit("acting runtime replay call site not found")

path.write_text(text, encoding="utf-8")
