from __future__ import annotations

import importlib.util

from nolane.metadata.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from nolane.metadata.manifests import build_component_manifests


COMPONENT_ID = "external.candidate_synthesis"
CANONICAL_MODULE = "nolane.external_core.candidate_synthesis"


def test_candidate_synthesis_is_declared_as_native_v001_component() -> None:
    assert importlib.util.find_spec(CANONICAL_MODULE) is not None, (
        "production change required: canonical candidate synthesis module is missing"
    )

    manifests = {row.component_id: row for row in build_component_manifests()}
    assert COMPONENT_ID in manifests
    manifest = manifests[COMPONENT_ID]
    assert str(manifest.version) == "0.0.1"
    assert manifest.layer == "external_core"
    assert manifest.state_schema == "candidate-synthesis-v1"

    ledger = build_component_implementation_ledger()
    record = ledger[COMPONENT_ID]
    assert record.status is ImplementationStatus.CANONICAL_NATIVE
    assert record.component_version == "0.0.1"
    assert record.canonical_module == CANONICAL_MODULE
    assert record.legacy_sources == ()
