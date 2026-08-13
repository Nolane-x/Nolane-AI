from __future__ import annotations
import hashlib, math, re
from collections import Counter
from typing import Protocol, Sequence
from .knowledge_types import KnowledgeDocument, EvidenceChunk
_TOKEN=re.compile(r"[\w]+",re.UNICODE)
def _terms(text:str): return [x.casefold() for x in _TOKEN.findall(text)]
def _ngrams(text:str,n:int=3):
    s=' '.join(_terms(text)); return Counter(s[i:i+n] for i in range(max(0,len(s)-n+1)))
def _cos(a:Counter,b:Counter):
    if not a or not b:return 0.0
    dot=sum(v*b.get(k,0) for k,v in a.items()); na=math.sqrt(sum(v*v for v in a.values())); nb=math.sqrt(sum(v*v for v in b.values()))
    return dot/(na*nb) if na and nb else 0.0
class KnowledgeSource(Protocol):
    def search(self,query:str,k:int=5)->list[EvidenceChunk]:...
class InMemoryKnowledgeStore:
    trainable_parameter_count=0
    def __init__(self,documents:Sequence[KnowledgeDocument],*,chunk_chars:int=800,overlap:int=80):
        if chunk_chars<64: raise ValueError('chunk_chars too small')
        self._rows=[]
        for doc in documents:
            start=0
            while start < len(doc.text):
                end=min(len(doc.text),start+chunk_chars); text=doc.text[start:end]
                sha=hashlib.sha256(text.encode()).hexdigest(); cid=hashlib.sha256(f'{doc.source_uri}|{doc.version}|{start}|{sha}'.encode()).hexdigest()[:24]
                self._rows.append((doc,start,end,text,sha,cid,_terms(text),_ngrams(text)))
                if end==len(doc.text): break
                start=max(start+1,end-overlap)
        self._df=Counter();
        for row in self._rows:
            self._df.update(set(row[6]))
        self._avgdl=sum(len(r[6]) for r in self._rows)/max(1,len(self._rows))
    def search(self,query:str,k:int=5):
        if not query.strip(): raise ValueError('query must be non-empty')
        if k<1: raise ValueError('k must be positive')
        q=_terms(query); qng=_ngrams(query); N=max(1,len(self._rows)); scored=[]
        for row in self._rows:
            doc,start,end,text,sha,cid,terms,ng=row; tf=Counter(terms); dl=max(1,len(terms)); lex=0.0
            for t in q:
                df=self._df.get(t,0); idf=math.log(1+(N-df+0.5)/(df+0.5)); f=tf.get(t,0); lex += idf*(f*2.2)/(f+1.2*(1-0.75+0.75*dl/max(1e-9,self._avgdl))) if f else 0.0
            sem=_cos(qng,ng); raw=lex+2.0*sem; utility=raw+0.25*float(doc.trust_score); scored.append((utility,lex,sem,float(doc.trust_score),cid,row))
        scored.sort(key=lambda x:(-x[0],-x[3],x[4])); top=scored[:k]; maxraw=max([x[0] for x in top] or [1.0])
        out=[]
        for raw,lex,sem,_trust,cid,row in top:
            doc,start,end,text,sha,_,_,_=row; norm=0.0 if maxraw<=0 else min(1.0,max(0.0,raw/maxraw))
            out.append(EvidenceChunk(cid,doc.document_id,doc.source_uri,text,sha,doc.version,start,end,norm,float(lex),float(sem),float(doc.trust_score)))
        return out
class CompositeKnowledgeStore:
    trainable_parameter_count=0
    def __init__(self,sources:Sequence[KnowledgeSource]): self.sources=tuple(sources)
    def search(self,query:str,k:int=5):
        rows=[]
        for source in self.sources: rows.extend(source.search(query,k=k))
        best={}
        for r in rows:
            prev=best.get(r.content_sha256)
            if prev is None or (r.score,r.trust_score,r.chunk_id)>(prev.score,prev.trust_score,prev.chunk_id): best[r.content_sha256]=r
        return sorted(best.values(),key=lambda r:(-r.score,-r.trust_score,r.chunk_id))[:k]
