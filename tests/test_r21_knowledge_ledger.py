from __future__ import annotations
import dataclasses, hashlib
import pytest

def chunk(cid,text,score=.8,trust=.9):
    from cogcoder.knowledge_types import EvidenceChunk
    return EvidenceChunk(cid,'d','mem://d',text,hashlib.sha256(text.encode()).hexdigest(),'1',0,len(text),score,score,0.0,trust)

def test_ledger_rejects_tampering_and_is_idempotent():
    from cogcoder.knowledge_ledger import EvidenceLedger
    led=EvidenceLedger(); c=chunk('c1','A --orbits--> B')
    assert led.ingest(c) is True
    assert led.ingest(c) is False
    bad=dataclasses.replace(c,chunk_id='bad',text='tampered')
    with pytest.raises(ValueError): led.ingest(bad)
    assert led.verify()

def test_conflicting_claims_are_retained_not_overwritten():
    from cogcoder.knowledge_ledger import EvidenceLedger
    led=EvidenceLedger()
    led.ingest(chunk('a','Nira --capital_of--> Vesta',trust=.95))
    led.ingest(chunk('b','Nira --capital_of--> Orin',trust=.65))
    conflicts=led.conflicts()
    assert len(conflicts)==1
    assert conflicts[0].subject=='Nira' and conflicts[0].relation=='capital_of'
    assert set(conflicts[0].objects)=={'Vesta','Orin'}
    assert len(led) == 2

def test_working_set_is_bounded_and_deterministic():
    from cogcoder.knowledge_ledger import EvidenceLedger
    led=EvidenceLedger()
    for i in range(8): led.ingest(chunk(f'c{i}',f'Node{i} --links--> Node{i+1}',score=.2+i/10,trust=.5+i/20))
    a=led.working_set(max_chunks=3,max_chars=1000); b=led.working_set(max_chunks=3,max_chars=1000)
    assert [x.chunk_id for x in a]==[x.chunk_id for x in b]
    assert len(a)==3
    assert sum(len(x.text) for x in a)<=1000
