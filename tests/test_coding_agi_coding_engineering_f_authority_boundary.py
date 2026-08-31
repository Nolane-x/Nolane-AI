import importlib

from nolane.metadata.implementation_status import ImplementationStatus, build_component_implementation_ledger


CANONICAL_F = {
    'external.coding.claims': 'nolane.external_core.coding_claims',
    'external.coding.patches': 'nolane.external_core.coding_patches',
    'external.coding.control': 'nolane.external_core.coding',
    'external.debugging': 'nolane.external_core.debugging',
    'external.ui_ux': 'nolane.external_core.ui_ux',
}

INTERNAL_COMPOSITION_MODULES = (
    'nolane.external_core.software_engineering',
    'nolane.external_core.software_engineering_control',
    'nolane.external_core.software_engineering_policy',
    'nolane.external_core.software_engineering_validity',
)

PROTOCOL_HELPERS = (
    'nolane.external_core.software_engineering_effects',
    'nolane.external_core.software_engineering_gate',
    'nolane.external_core.software_engineering_mutation',
    'nolane.external_core.software_engineering_receipts',
)


def test_f_keeps_exact_existing_canonical_authorities_and_does_not_register_shadow_components():
    implementation = build_component_implementation_ledger()
    for component_id, canonical_module in CANONICAL_F.items():
        row = implementation[component_id]
        assert row.status is ImplementationStatus.CANONICAL_NATIVE
        assert row.canonical_write_authority
        assert row.canonical_module == canonical_module
        module = importlib.import_module(canonical_module)
        assert module.COMPONENT_ID == component_id

    for module_name in INTERNAL_COMPOSITION_MODULES:
        module = importlib.import_module(module_name)
        internal_id = getattr(module, 'COMPONENT_ID')
        assert internal_id.startswith('external.software_engineering')
        assert internal_id not in implementation

    for module_name in PROTOCOL_HELPERS:
        module = importlib.import_module(module_name)
        assert not hasattr(module, 'COMPONENT_ID')
        assert str(module.PROTOCOL_ID).startswith('external.software_engineering')


def test_f_composition_never_claims_canonical_or_promotion_authority_by_metadata():
    implementation = build_component_implementation_ledger()
    shadow_ids = {
        getattr(importlib.import_module(module_name), 'COMPONENT_ID')
        for module_name in INTERNAL_COMPOSITION_MODULES
    }
    assert shadow_ids.isdisjoint(implementation)
    assert all(component_id in implementation for component_id in CANONICAL_F)
