import pytest

from nolane.neural.core_contract import EvidenceRef, NeuralInvariantError


def test_live_evidence_source_core_rejects_stringifiable_non_string_identity():
    with pytest.raises(NeuralInvariantError, match="source_core.*exact string"):
        EvidenceRef.create(
            source_core=123,
            receipt_id="receipt-1",
            digest="a" * 64,
            authority="observation",
        )


def test_live_evidence_receipt_id_rejects_stringifiable_non_string_identity():
    with pytest.raises(NeuralInvariantError, match="receipt_id.*exact string"):
        EvidenceRef.create(
            source_core="memory",
            receipt_id=123,
            digest="a" * 64,
            authority="observation",
        )


def test_live_evidence_authority_rejects_stringifiable_non_string_identity():
    with pytest.raises(NeuralInvariantError, match="authority.*exact string"):
        EvidenceRef.create(
            source_core="memory",
            receipt_id="receipt-1",
            digest="a" * 64,
            authority=123,
        )


def test_live_evidence_digest_rejects_stringifiable_non_string_digest():
    with pytest.raises(NeuralInvariantError, match="digest.*exact string"):
        EvidenceRef.create(
            source_core="memory",
            receipt_id="receipt-1",
            digest=int("1" * 64),
            authority="observation",
        )
