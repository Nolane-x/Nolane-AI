from __future__ import annotations

import runpy
from pathlib import Path


runpy.run_path(".github/e_acting_effect_authority_patch_v2.py", run_name="__main__")


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8")
    if old not in source:
        raise SystemExit(f"v3 patch anchor missing in {path}: {old[:120]!r}")
    if source.count(old) != 1:
        raise SystemExit(f"v3 patch anchor is not unique in {path}: {old[:120]!r}")
    file_path.write_text(source.replace(old, new, 1), encoding="utf-8")


# Replace implementation-literal assertions with architectural delegation
# contracts. The classifier behavior itself is covered by
# test_refoundation_acting_effect_authority.py.
replace_once(
    "tests/test_refoundation_acting_runtime.py",
    '''def test_canonical_adapter_uses_risk_appropriate_verifier_levels() -> None:\n    source = inspect.getsource(OrganizationExecutionControlPlane.step)\n    assert "verifier_level = VerifierLevel.V2" in source\n    assert "verifier_level = VerifierLevel.V3" in source\n    assert "verifier_level = VerifierLevel.V1" in source\n    assert "verifier_level=verifier_level" in source\n\n\ndef test_external_effect_classification_precedes_local_mutation_rollback_hints() -> None:\n    source = inspect.getsource(OrganizationExecutionControlPlane.step)\n    external_branch = (\n        "\\n            if is_external or action.tool_action.tool_id in unconfined_process_tools:"\n        "\\n                effect_class = EffectClass.EXTERNAL_MUTATION"\n    )\n    local_branch = "\\n            elif action.tool_action.mutation_paths:\\n                effect_class = EffectClass.LOCAL_MUTATION"\n    assert external_branch in source\n    assert local_branch in source\n    assert source.index(external_branch) < source.index(local_branch)\n\n\ndef test_unconfined_process_tools_use_external_like_risk_floor() -> None:\n    source = inspect.getsource(OrganizationExecutionControlPlane.step)\n    assert "unconfined_process_tools = frozenset({'terminal', 'compiler', 'test-runner'})" in source\n    assert "if is_external or action.tool_action.tool_id in unconfined_process_tools:" in source\n''',
    '''def test_canonical_adapter_delegates_effect_risk_and_verifier_authority_to_transactional_runtime() -> None:\n    source = inspect.getsource(OrganizationExecutionControlPlane.step)\n    assert "effect_class = self.acting_executor.minimum_effect_class(action.tool_action)" in source\n    assert "risk_class = minimum_risk_for_effect(effect_class)" in source\n    assert "verifier_level = self.acting_executor.protocol.minimum_verifier_level(risk_class)" in source\n    assert "verifier_level=verifier_level" in source\n\n\ndef test_canonical_adapter_does_not_reintroduce_parallel_effect_classifier() -> None:\n    source = inspect.getsource(OrganizationExecutionControlPlane.step)\n    assert "unconfined_process_tools" not in source\n    assert "elif action.tool_action.mutation_paths" not in source\n    assert "self.acting_executor.minimum_effect_class(action.tool_action)" in source\n''',
)

replace_once(
    "tests/test_refoundation_wave5aa_native_execution_control.py",
    '''    assert row.component_version == "0.0.5"\n    assert str(component_version("external.execution.control")) == "0.0.5"''',
    '''    assert row.component_version == "0.0.6"\n    assert str(component_version("external.execution.control")) == "0.0.6"''',
)
