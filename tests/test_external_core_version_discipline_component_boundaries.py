from __future__ import annotations

from nolane.metadata.version_discipline import discover_component_ownership


def test_canonical_component_dependency_change_does_not_bump_consumers() -> None:
    sources = {
        "nolane.external_core.evidence": 'COMPONENT_ID = "external.evidence"\nVALUE = 2\n',
        "nolane.external_core.integration": (
            'from nolane.external_core.evidence import VALUE\n'
            'COMPONENT_ID = "external.integration"\n'
            'INTEGRATION_VALUE = VALUE\n'
        ),
        "nolane.external_core.coding_control": (
            'from nolane.external_core.integration import INTEGRATION_VALUE\n'
            'COMPONENT_ID = "external.coding.control"\n'
        ),
    }
    ownership = discover_component_ownership(
        sources,
        {"nolane.external_core.evidence"},
        {"external.evidence", "external.integration", "external.coding.control"},
    )
    assert ownership == {"nolane.external_core.evidence": ("external.evidence",)}


def test_unowned_shared_helper_still_propagates_to_all_reachable_owners() -> None:
    sources = {
        "nolane.external_core.evidence": (
            'from nolane.external_core._shared_protocol import VALUE\n'
            'COMPONENT_ID = "external.evidence"\n'
        ),
        "nolane.external_core.integration": (
            'from nolane.external_core._shared_protocol import VALUE\n'
            'COMPONENT_ID = "external.integration"\n'
        ),
        "nolane.external_core._shared_protocol": 'VALUE = 2\n',
    }
    ownership = discover_component_ownership(
        sources,
        {"nolane.external_core._shared_protocol"},
        {"external.evidence", "external.integration"},
    )
    assert ownership == {
        "nolane.external_core._shared_protocol": ("external.evidence", "external.integration"),
    }
