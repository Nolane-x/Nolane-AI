from pathlib import Path

execution_path = Path("nolane/external_core/execution.py")
text = execution_path.read_text(encoding="utf-8")

old_version = 'COMPONENT_VERSION = "0.0.9"'
new_version = 'COMPONENT_VERSION = "0.0.10"'
if old_version in text:
    text = text.replace(old_version, new_version, 1)
elif new_version not in text:
    raise SystemExit("unexpected execution control version")

anchor = '''    def _expected_core_contract_digest(self, tool_id: str) -> str:\n        if str(tool_id) not in frozenset(getattr(self.executor, 'external_core_ids', ())):\n            return ''\n        return self.external_cores.get(str(tool_id)).contract_digest\n\n'''
helper = '''    def _expected_core_contract_digest(self, tool_id: str) -> str:\n        if str(tool_id) not in frozenset(getattr(self.executor, 'external_core_ids', ())):\n            return ''\n        return self.external_cores.get(str(tool_id)).contract_digest\n\n    def _attest_committed_core_receipt(\n        self,\n        *,\n        row: Any,\n        session: ExecutionSession,\n    ) -> Any:\n        receipt_id = str(row.outcome_ref).strip()\n        if not receipt_id or str(row.commit_ref).strip() != receipt_id:\n            raise ValueError(\n                'committed acting core receipt authority mismatch: commit_ref'\n            )\n        try:\n            core = self.executor.get_receipt(receipt_id)\n        except Exception as exc:\n            raise ValueError('committed acting action references unavailable core receipt') from exc\n\n        to_state = getattr(core, 'to_state', None)\n        from_state = getattr(type(core), 'from_state', None)\n        if callable(to_state) and callable(from_state):\n            try:\n                canonical = from_state(to_state())\n            except Exception as exc:\n                raise ValueError(\n                    'committed acting core receipt integrity validation failed'\n                ) from exc\n            if canonical != core:\n                raise ValueError('committed acting core receipt integrity validation failed')\n\n        expected_workspace_digest = self._persisted_workspace_fence(session)\n        expected = {\n            'receipt_id': receipt_id,\n            'agent_id': session.agent_id,\n            'task_id': session.task_id,\n            'tool_id': row.contract.core_id,\n            'operation': row.contract.operation,\n            'input_digest': row.contract.input_digest,\n        }\n        if expected_workspace_digest is not None:\n            expected['before_workspace_digest'] = expected_workspace_digest\n        mismatches = [\n            field\n            for field, expected_value in expected.items()\n            if str(getattr(core, field, '')) != str(expected_value)\n        ]\n        if getattr(core, 'authorized', None) is not True:\n            mismatches.append('authorized')\n        if getattr(core, 'success', None) is not True:\n            mismatches.append('success')\n\n        if session.execution_proof_version >= 2:\n            expected_core_digest = self._expected_core_contract_digest(row.contract.core_id)\n            if str(getattr(core, 'workspace_epoch_id', '')) != str(session.workspace_epoch_id):\n                mismatches.append('workspace_epoch_id')\n            if str(getattr(core, 'core_contract_digest', '')) != expected_core_digest:\n                mismatches.append('core_contract_digest')\n            if row.contract.workspace_epoch_id != session.workspace_epoch_id:\n                mismatches.append('contract_workspace_epoch_id')\n            if row.contract.core_contract_digest != expected_core_digest:\n                mismatches.append('contract_core_contract_digest')\n\n        if mismatches:\n            raise ValueError(\n                'committed acting core receipt authority mismatch: '\n                + ', '.join(dict.fromkeys(mismatches))\n            )\n        return core\n\n'''
if anchor in text:
    text = text.replace(anchor, helper, 1)
elif helper not in text:
    raise SystemExit("execution authority helper anchor not found")

old_block = '''            if row.phase is ActionPhase.COMMITTED:\n                if not row.outcome_ref:\n                    raise ValueError('committed acting action is missing its core receipt')\n                try:\n                    core = self.executor.get_receipt(row.outcome_ref)\n                except Exception as exc:\n                    raise ValueError('committed acting action references unavailable core receipt') from exc\n                if not bool(core.success):\n                    raise ValueError('committed acting action references unsuccessful core receipt')\n                expected_workspace_digest = self._persisted_workspace_fence(session)\n                if (\n                    expected_workspace_digest is not None\n                    and str(core.before_workspace_digest) != expected_workspace_digest\n                ):\n                    raise ValueError('committed acting action workspace fence mismatch')\n                if session.execution_proof_version >= 2:\n                    expected_core_digest = self._expected_core_contract_digest(row.contract.core_id)\n                    if str(getattr(core, 'workspace_epoch_id', '')) != str(session.workspace_epoch_id):\n                        raise ValueError('committed acting action workspace epoch mismatch')\n                    if str(getattr(core, 'core_contract_digest', '')) != expected_core_digest:\n                        raise ValueError('committed acting action core contract mismatch')\n                    if row.contract.workspace_epoch_id != session.workspace_epoch_id:\n                        raise ValueError('committed acting contract workspace epoch mismatch')\n                    if row.contract.core_contract_digest != expected_core_digest:\n                        raise ValueError('committed acting contract core contract mismatch')\n                committed_receipts[row.action_id] = core\n'''
new_block = '''            if row.phase is ActionPhase.COMMITTED:\n                core = self._attest_committed_core_receipt(row=row, session=session)\n                committed_receipts[row.action_id] = core\n'''
if old_block in text:
    text = text.replace(old_block, new_block, 1)
elif new_block not in text:
    raise SystemExit("committed recovery preflight block not found")

execution_path.write_text(text, encoding="utf-8")

metadata_path = Path("nolane/metadata/component_versions.py")
metadata = metadata_path.read_text(encoding="utf-8")
old_revision = '        "external.execution.control": 9,'
new_revision = '        "external.execution.control": 10,'
if old_revision in metadata:
    metadata = metadata.replace(old_revision, new_revision, 1)
elif new_revision not in metadata:
    raise SystemExit("unexpected execution control metadata revision")
metadata_path.write_text(metadata, encoding="utf-8")

canonical_test_path = Path("tests/test_refoundation_wave5aa_native_execution_control.py")
canonical_test = canonical_test_path.read_text(encoding="utf-8")
canonical_test = canonical_test.replace('canonical.COMPONENT_VERSION == "0.0.9"', 'canonical.COMPONENT_VERSION == "0.0.10"')
canonical_test = canonical_test.replace('row.component_version == "0.0.9"', 'row.component_version == "0.0.10"')
canonical_test = canonical_test.replace('component_version("external.execution.control")) == "0.0.9"', 'component_version("external.execution.control")) == "0.0.10"')
if '0.0.9' in canonical_test:
    raise SystemExit("stale execution-control version assertion remains")
canonical_test_path.write_text(canonical_test, encoding="utf-8")
