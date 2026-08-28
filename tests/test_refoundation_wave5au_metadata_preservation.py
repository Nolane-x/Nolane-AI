from __future__ import annotations

from cogcoder.refoundation.implementation_status import build_component_implementation_ledger


def test_wave5au_preserves_preexisting_native_implementation_metadata() -> None:
    ledger = build_component_implementation_ledger()

    assert "canonical JSON serialization and SHA-256 content identity" in ledger["core.canonical_digest"].notes
    assert "twelve-profile routing" in ledger["external.operations"].notes
    assert "seven-module evaluation-campaign authority" in ledger["evaluation.campaign"].notes


def test_wave5au_only_changes_cognitive_library_implementation_ownership() -> None:
    row = build_component_implementation_ledger()["external.cognitive_library"]

    assert row.canonical_module == "nolane.external_core.cognitive_library"
    assert row.canonical_write_authority
    assert "R2.53/R2.56/R2.57" in row.notes
