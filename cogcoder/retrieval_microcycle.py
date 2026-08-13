from __future__ import annotations
from dataclasses import dataclass, field
import re
from .knowledge_ledger import EvidenceLedger
from .knowledge_types import EvidenceChunk
from .knowledge_store import KnowledgeSource
_CLAIM=re.compile(r'^\s*(.+?)\s+--([^>-]+)-->\s+(.+?)\s*$')
@dataclass(frozen=True)
class KnowledgeNeed:
    query:str; uncertainty:float; query_drift:float; novelty:float=1.0; use_anchors:bool=False; force:bool=False
@dataclass
class RetrievalState:
    calls:int=0; retrieved_chars:int=0; anchors:list[str]=field(default_factory=list); last_query:str=''; seen_chunk_ids:set[str]=field(default_factory=set)
@dataclass(frozen=True)
class RetrievalDecision:
    retrieved:bool; reason:str; query:str; chunks:tuple[EvidenceChunk,...]=(); call_index:int=0
class CognitionTimeRetriever:
    trainable_parameter_count=0
    def __init__(self,source:KnowledgeSource,*,max_calls:int=8,top_k:int=3,max_chars:int=12000,uncertainty_threshold:float=.25,drift_threshold:float=.15):
        if max_calls<0 or top_k<1 or max_chars<1: raise ValueError('invalid retrieval budget')
        self.source=source; self.max_calls=max_calls; self.top_k=top_k; self.max_chars=max_chars; self.uncertainty_threshold=uncertainty_threshold; self.drift_threshold=drift_threshold
        self.state=RetrievalState(); self.ledger=EvidenceLedger()
    def _query(self,need:KnowledgeNeed):
        q=need.query.strip()
        if not q: raise ValueError('knowledge query must be non-empty')
        if need.use_anchors and self.state.anchors:
            q=(q+' '+' '.join(self.state.anchors[-2:])).strip()
        return q
    def _add_anchors(self,text:str):
        m=_CLAIM.match(text.strip())
        if m:
            for value in (m.group(1).strip(),m.group(3).strip()):
                if value and value not in self.state.anchors: self.state.anchors.append(value)
    def step(self,need:KnowledgeNeed)->RetrievalDecision:
        q=self._query(need)
        if self.state.calls>=self.max_calls: return RetrievalDecision(False,'call_budget_exhausted',q,call_index=self.state.calls)
        if not need.force and need.uncertainty < self.uncertainty_threshold and need.query_drift < self.drift_threshold:
            self.state.last_query=q; return RetrievalDecision(False,'stable_confident',q,call_index=self.state.calls)
        if self.state.retrieved_chars>=self.max_chars: return RetrievalDecision(False,'character_budget_exhausted',q,call_index=self.state.calls)
        self.state.calls += 1; rows=self.source.search(q,k=max(self.top_k, self.top_k+len(self.state.seen_chunk_ids))); novel=[]
        for row in rows:
            if row.chunk_id in self.state.seen_chunk_ids: continue
            if self.state.retrieved_chars+len(row.text)>self.max_chars: continue
            self.state.seen_chunk_ids.add(row.chunk_id); self.state.retrieved_chars += len(row.text); self.ledger.ingest(row); self._add_anchors(row.text); novel.append(row)
            if len(novel) >= self.top_k: break
        self.state.last_query=q
        if not novel: return RetrievalDecision(False,'no_novel_evidence',q,call_index=self.state.calls)
        return RetrievalDecision(True,'retrieved',q,tuple(novel),self.state.calls)
