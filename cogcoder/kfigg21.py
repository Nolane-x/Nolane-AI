from __future__ import annotations
from dataclasses import dataclass
import random,re
from .knowledge_types import KnowledgeDocument, EvidenceChunk
from .knowledge_store import InMemoryKnowledgeStore
from .knowledge_ledger import EvidenceLedger
from .retrieval_microcycle import CognitionTimeRetriever, KnowledgeNeed
_CLAIM=re.compile(r'^\s*(.+?)\s+--next-->\s+(.+?)\s*$')

@dataclass(frozen=True)
class KFIGG21Case:
    seed:int; question:str; start:str; answer:str; chain:tuple[tuple[str,str],...]; documents:tuple[KnowledgeDocument,...]
@dataclass(frozen=True)
class KFIGG21Result:
    answer:str|None; correct:bool; retrieval_calls:int; retrieved_chunks:int; retrieved_chars:int; chunk_budget:int; provenance_ok:bool; trace:tuple[str,...]

def _name(rng:random.Random,prefix:str,index:int)->str:
    alphabet='ABCDEFGHJKLMNPQRSTUVWXYZ'
    return f'{prefix}{alphabet[rng.randrange(len(alphabet))]}{rng.randrange(1000,9999)}_{index}'

def make_kfigg21_case(*,seed:int,hops:int|None=None,distractors:int=36,contradictions:int=3)->KFIGG21Case:
    rng=random.Random(int(seed)); hops=int(hops or rng.randint(2,4))
    if not 2<=hops<=4: raise ValueError('hops must be 2..4')
    nodes=[_name(rng,'N',i) for i in range(hops+1)]; chain=tuple((nodes[i],nodes[i+1]) for i in range(hops)); docs=[]
    for i,(a,b) in enumerate(chain): docs.append(KnowledgeDocument(f'true-{i}',f'kfigg://{seed}/true/{i}',f'{a} --next--> {b}',version='1',trust_score=.99))
    for i in range(distractors):
        a=_name(rng,'D',i); b=_name(rng,'X',i); docs.append(KnowledgeDocument(f'd-{i}',f'kfigg://{seed}/d/{i}',f'{a} --next--> {b}',version='1',trust_score=.72))
    # Low-trust contradictions test that relevance and truth confidence remain separate.
    for i in range(min(contradictions,hops)):
        a=chain[i][0]; wrong=_name(rng,'W',i); docs.append(KnowledgeDocument(f'c-{i}',f'kfigg://{seed}/c/{i}',f'{a} --next--> {wrong}',version='obsolete',trust_score=.15))
    rng.shuffle(docs)
    question=f'Trace the next-link route beginning at {nodes[0]} for exactly {hops} hops. Which entity is reached?'
    return KFIGG21Case(int(seed),question,nodes[0],nodes[-1],chain,tuple(docs))

def _parse(chunk:EvidenceChunk):
    m=_CLAIM.match(chunk.text.strip()); return (m.group(1).strip(),m.group(2).strip()) if m else None

def _resolve(chunks:list[EvidenceChunk]|tuple[EvidenceChunk,...],start:str,hops:int):
    options={}
    for c in chunks:
        p=_parse(c)
        if not p: continue
        a,b=p; cur=options.get(a)
        if cur is None or (c.trust_score,c.score,c.chunk_id)>(cur[0].trust_score,cur[0].score,cur[0].chunk_id): options[a]=(c,b)
    current=start; trace=[]
    for _ in range(hops):
        if current not in options: return None,tuple(trace)
        c,current=options[current]; trace.append(c.chunk_id)
    return current,tuple(trace)

def solve_retrieve_once(case:KFIGG21Case,*,top_k:int=1,max_calls:int=4)->KFIGG21Result:
    budget=int(top_k)*int(max_calls); store=InMemoryKnowledgeStore(case.documents,chunk_chars=256)
    chunks=store.search(case.question,k=budget); ledger=EvidenceLedger()
    for c in chunks: ledger.ingest(c)
    answer,trace=_resolve(chunks,case.start,len(case.chain))
    return KFIGG21Result(answer,answer==case.answer,1,len(chunks),sum(len(c.text) for c in chunks),budget,ledger.verify(),trace)

def solve_interleaved(case:KFIGG21Case,*,top_k:int=1,max_calls:int=4)->KFIGG21Result:
    store=InMemoryKnowledgeStore(case.documents,chunk_chars=256); retriever=CognitionTimeRetriever(store,max_calls=max_calls,top_k=top_k,max_chars=100000)
    current=case.start; trace=[]; all_chunks=[]
    for hop in range(len(case.chain)):
        decision=retriever.step(KnowledgeNeed(f'{current} next',uncertainty=1.0,query_drift=1.0,force=True))
        all_chunks.extend(decision.chunks)
        candidates=[]
        for c in decision.chunks:
            p=_parse(c)
            if p and p[0]==current: candidates.append((c,p[1]))
        if not candidates: return KFIGG21Result(None,False,retriever.state.calls,len(all_chunks),retriever.state.retrieved_chars,top_k*max_calls,retriever.ledger.verify(),tuple(trace))
        c,current=max(candidates,key=lambda x:(x[0].trust_score,x[0].score,x[0].chunk_id)); trace.append(c.chunk_id)
    return KFIGG21Result(current,current==case.answer,retriever.state.calls,len(all_chunks),retriever.state.retrieved_chars,top_k*max_calls,retriever.ledger.verify(),tuple(trace))

def evaluate_kfigg21(*,seeds,top_k:int=1,max_calls:int=4,distractors:int=36):
    rows=[]
    for seed in seeds:
        case=make_kfigg21_case(seed=int(seed),distractors=distractors)
        once=solve_retrieve_once(case,top_k=top_k,max_calls=max_calls); inter=solve_interleaved(case,top_k=top_k,max_calls=max_calls)
        rows.append((case,once,inter))
    n=len(rows); once_ok=sum(x[1].correct for x in rows); inter_ok=sum(x[2].correct for x in rows)
    return {'cases':n,'retrieve_once_solved':once_ok,'interleaved_solved':inter_ok,'retrieve_once_solve_rate':once_ok/max(1,n),'interleaved_solve_rate':inter_ok/max(1,n),'gain_pp':100*(inter_ok-once_ok)/max(1,n),'provenance_failures':sum((not x[1].provenance_ok)+(not x[2].provenance_ok) for x in rows),'rows':rows}
