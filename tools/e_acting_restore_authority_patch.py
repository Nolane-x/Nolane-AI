from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_execution() -> None:
    path = ROOT / "nolane/external_core/execution.py"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        'COMPONENT_VERSION = "0.0.11"',
        'COMPONENT_VERSION = "0.0.12"',
        label="execution component version",
    )

    text = replace_once(
        text,
        "class OrganizationExecutionControlPlane:\n    def __init__(\n",
        "class OrganizationExecutionControlPlane:\n"
        "    @staticmethod\n"
        "    def _index_unique_authority(\n"
        "        rows: Sequence[Any],\n"
        "        *,\n"
        "        id_attr: str,\n"
        "        kind: str,\n"
        "    ) -> dict[str, Any]:\n"
        "        indexed: dict[str, Any] = {}\n"
        "        for row in rows:\n"
        "            row_id = str(getattr(row, id_attr))\n"
        "            if row_id in indexed:\n"
        "                raise ValueError(f'duplicate execution {kind} authority id: {row_id}')\n"
        "            indexed[row_id] = row\n"
        "        return indexed\n\n"
        "    def __init__(\n",
        label="unique authority index helper",
    )

    text = replace_once(
        text,
        "        self._sessions = {row.session_id: row for row in sessions}\n"
        "        self._decisions = {row.receipt_id: row for row in decisions}\n"
        "        self._steps = {row.receipt_id: row for row in steps}\n"
        "        self._terminals = {row.receipt_id: row for row in terminals}\n",
        "        self._sessions = self._index_unique_authority(\n"
        "            sessions, id_attr='session_id', kind='session'\n"
        "        )\n"
        "        self._decisions = self._index_unique_authority(\n"
        "            decisions, id_attr='receipt_id', kind='decision'\n"
        "        )\n"
        "        self._steps = self._index_unique_authority(\n"
        "            steps, id_attr='receipt_id', kind='step'\n"
        "        )\n"
        "        self._terminals = self._index_unique_authority(\n"
        "            terminals, id_attr='receipt_id', kind='terminal'\n"
        "        )\n",
        label="authority indexes",
    )

    text = replace_once(
        text,
        "            first_workspace_digest: str | None = None\n"
        "            previous_workspace_digest: str | None = None\n"
        "            for receipt_id in session.step_receipt_ids:\n",
        "            first_workspace_digest: str | None = None\n"
        "            previous_workspace_digest: str | None = None\n"
        "            projected_core_receipt_ids: list[str] = []\n"
        "            for receipt_id in session.step_receipt_ids:\n",
        label="core projection accumulator",
    )

    text = replace_once(
        text,
        "                if step.core_receipt_id is not None and step.core_receipt_id not in session.core_receipt_ids:\n"
        "                    raise ValueError('execution step receipt core binding mismatch')\n",
        "                if step.core_receipt_id is not None:\n"
        "                    projected_core_receipt_ids.append(step.core_receipt_id)\n"
        "                    if step.core_receipt_id not in session.core_receipt_ids:\n"
        "                        raise ValueError('execution step receipt core binding mismatch')\n",
        label="core projection collection",
    )

    text = replace_once(
        text,
        "                previous_workspace_digest = step.after_workspace_digest\n\n"
        "            if session.workspace_provenance_version >= 2:\n",
        "                previous_workspace_digest = step.after_workspace_digest\n\n"
        "            if tuple(projected_core_receipt_ids) != session.core_receipt_ids:\n"
        "                raise ValueError('execution session core receipt projection mismatch')\n\n"
        "            if session.workspace_provenance_version >= 2:\n",
        label="core projection closure",
    )

    text = replace_once(
        text,
        "                if terminal.output_artifact_ids != session.output_artifact_ids:\n"
        "                    raise ValueError('execution terminal receipt output-history mismatch')\n"
        "        if self._session_counter < max_counter:\n",
        "                if terminal.output_artifact_ids != session.output_artifact_ids:\n"
        "                    raise ValueError('execution terminal receipt output-history mismatch')\n\n"
        "        for receipt_id in self._decisions:\n"
        "            if receipt_id not in decision_owners:\n"
        "                raise ValueError(f'unowned execution decision receipt: {receipt_id}')\n"
        "        for receipt_id in self._steps:\n"
        "            if receipt_id not in step_owners:\n"
        "                raise ValueError(f'unowned execution step receipt: {receipt_id}')\n"
        "        for receipt_id in self._terminals:\n"
        "            if receipt_id not in terminal_owners:\n"
        "                raise ValueError(f'unowned execution terminal receipt: {receipt_id}')\n\n"
        "        if self._session_counter < max_counter:\n",
        label="inverse ownership closure",
    )

    path.write_text(text, encoding="utf-8")


def patch_versions() -> None:
    metadata = ROOT / "nolane/metadata/component_versions.py"
    text = metadata.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '        "external.execution.control": 11,',
        '        "external.execution.control": 12,',
        label="metadata execution-control revision",
    )
    metadata.write_text(text, encoding="utf-8")

    tests = ROOT / "tests/test_refoundation_component_versions.py"
    text = tests.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '    "external.execution.control": 11,',
        '    "external.execution.control": 12,',
        label="accepted execution-control revision",
    )
    text = replace_once(
        text,
        '    assert str(component_version("external.execution.control")) == "0.0.11"',
        '    assert str(component_version("external.execution.control")) == "0.0.12"',
        label="execution-control current version assertion",
    )
    text = replace_once(
        text,
        '    assert str(next_component_version("external.execution.control")) == "0.0.12"',
        '    assert str(next_component_version("external.execution.control")) == "0.0.13"',
        label="execution-control next version assertion",
    )
    tests.write_text(text, encoding="utf-8")

    wave5aa = ROOT / "tests/test_refoundation_wave5aa_native_execution_control.py"
    text = wave5aa.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '    assert canonical.COMPONENT_VERSION == "0.0.11"',
        '    assert canonical.COMPONENT_VERSION == "0.0.12"',
        label="Wave 5AA canonical execution-control version",
    )
    text = replace_once(
        text,
        '    assert row.component_version == "0.0.11"\n    assert str(component_version("external.execution.control")) == "0.0.11"',
        '    assert row.component_version == "0.0.12"\n    assert str(component_version("external.execution.control")) == "0.0.12"',
        label="Wave 5AA authority version facade",
    )
    wave5aa.write_text(text, encoding="utf-8")


def main() -> None:
    patch_execution()
    patch_versions()


if __name__ == "__main__":
    main()
