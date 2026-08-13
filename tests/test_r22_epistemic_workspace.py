import hashlib

from cogcoder.knowledge_types import EvidenceChunk
from cogcoder.epistemic_workspace import EpistemicWorkspace


def chunk(text, *, cid, source, version, trust=.9, score=.8):
    return EvidenceChunk(cid, cid, source, text, hashlib.sha256(text.encode()).hexdigest(), version, 0, len(text), score, score, score, trust)


def test_newer_same_source_version_supersedes_older_claim():
    ws = EpistemicWorkspace()
    ws.ingest(chunk('alpha --next--> old', cid='old', source='kb://route', version='1', trust=.99))
    ws.ingest(chunk('alpha --next--> new', cid='new', source='kb://route', version='2', trust=.80))
    belief = ws.belief('alpha', 'next')
    assert belief.object == 'new'
    assert belief.contested is False
    assert belief.evidence_chunk_ids == ('new',)
    assert 'old' in belief.superseded_chunk_ids


def test_independent_sources_corroborate_without_erasing_conflict():
    ws = EpistemicWorkspace()
    ws.ingest(chunk('alpha --next--> beta', cid='a', source='kb://one', version='3', trust=.82))
    ws.ingest(chunk('alpha --next--> beta', cid='b', source='kb://two', version='1', trust=.81))
    ws.ingest(chunk('alpha --next--> gamma', cid='c', source='kb://three', version='4', trust=.88))
    belief = ws.belief('alpha', 'next')
    assert belief.object == 'beta'
    assert belief.independent_sources == 2
    assert set(belief.alternatives) == {'gamma'}
    assert ws.conflicts()


def test_provenance_verification_fails_closed_on_mutated_chunk():
    ws = EpistemicWorkspace()
    good = chunk('alpha --next--> beta', cid='a', source='kb://one', version='1')
    ws.ingest(good)
    assert ws.verify_provenance()
    object.__setattr__(good, 'text', 'alpha --next--> tampered')
    assert ws.verify_provenance() is False


def test_unresolved_or_contested_claim_produces_narrow_followup_query():
    ws = EpistemicWorkspace()
    assert ws.missing_queries('alpha', 'next') == ('alpha next current authoritative',)
    ws.ingest(chunk('alpha --next--> beta', cid='a', source='kb://one', version='1', trust=.8, score=.8))
    ws.ingest(chunk('alpha --next--> gamma', cid='b', source='kb://two', version='1', trust=.8, score=.8))
    belief = ws.belief('alpha', 'next')
    assert belief.contested is True
    queries = ws.missing_queries('alpha', 'next')
    assert len(queries) == 1
    assert 'alpha next' in queries[0]
    assert 'beta' in queries[0] and 'gamma' in queries[0]
