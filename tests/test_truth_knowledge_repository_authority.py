from __future__ import annotations

import importlib
from pathlib import Path

from nolane.external_core import assurance, epistemic, evidence, verification
from nolane.memory import knowledge


CANONICAL_A = {
    "external.evidence": evidence,
    "external.knowledge": knowledge,
    "external.epistemic": epistemic,
    "external.verification": verification,
    "external.assurance": assurance,
}


def test_a_layer_has_exactly_one_canonical_authority_per_declared_component():
    assert {module.COMPONENT_ID for module in CANONICAL_A.values()} == set(CANONICAL_A)
    assert len({module.COMPONENT_ID for module in CANONICAL_A.values()}) == 5


def test_truth_protocol_helpers_do_not_redeclare_canonical_component_ids():
    helper_names = {
        "nolane.external_core.evidence_truth": "external.evidence",
        "nolane.external_core.knowledge_truth": "external.knowledge",
        "nolane.external_core.epistemic_truth": "external.epistemic",
        "nolane.external_core.verification_truth": "external.verification",
        "nolane.external_core.assurance_truth": "external.assurance",
    }
    for module_name, parent_id in helper_names.items():
        module = importlib.import_module(module_name)
        assert not hasattr(module, "COMPONENT_ID")
        assert module.PARENT_COMPONENT_ID == parent_id


def test_truth_knowledge_protocol_module_is_unambiguous_and_old_duplicate_path_is_gone():
    assert Path("nolane/external_core/knowledge_truth.py").is_file()
    assert not Path("nolane/external_core/knowledge.py").exists()


def test_truth_protocol_uses_repository_canonical_digest_instead_of_private_digest_authority():
    assert not Path("nolane/external_core/_truth_digest.py").exists()
    for path in (
        "nolane/external_core/evidence_truth.py",
        "nolane/external_core/knowledge_truth.py",
        "nolane/external_core/epistemic_truth.py",
        "nolane/external_core/verification_truth.py",
        "nolane/external_core/assurance_truth.py",
    ):
        text = Path(path).read_text(encoding="utf-8")
        assert "from nolane.core.canonical_digest import canonical_digest" in text
        assert "_truth_digest" not in text


def test_truth_protocol_parent_components_are_registered_canonical_native_authorities():
    from nolane.metadata.implementation_status import ImplementationStatus, build_component_implementation_ledger

    ledger = build_component_implementation_ledger()
    for component_id, module in CANONICAL_A.items():
        row = ledger[component_id]
        assert row.status is ImplementationStatus.CANONICAL_NATIVE
        assert row.canonical_write_authority
        assert row.canonical_module == module.__name__
