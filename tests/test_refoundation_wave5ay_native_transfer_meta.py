from __future__ import annotations

import importlib


def test_wave5ay_native_transfer_meta_authority_exists() -> None:
    module = importlib.import_module("nolane.external_core.transfer_meta")

    assert module.COMPONENT_ID == "external.transfer_meta"
    assert module.COMPONENT_VERSION == "0.0.1"
    assert module.MIGRATED_FROM == "cogcoder R2.69 autonomous transfer/meta-learning lineage"

    expected = {
        "PortableExperience",
        "PortableExperienceSourceReceipt",
        "TransferAdaptation",
        "TransferState",
        "TransferRecord",
        "TransferMetaGovernor",
    }
    assert expected.issubset(set(module.__all__))
