from __future__ import annotations
import hashlib,re
from .knowledge_types import KnowledgeDocument,EvidenceChunk
from .knowledge_store import InMemoryKnowledgeStore

class CallbackKnowledgeSource:
    """Host bridge for live web/files/vector-DB/database retrieval.

    This adapter is intentionally outside the FRESH-locked R2.1a retrieval core.
    It normalizes host results into provenance-bound EvidenceChunk records.
    """
    trainable_parameter_count=0
    def __init__(self,search_fn):
        if not callable(search_fn): raise TypeError('search_fn must be callable')
        self.search_fn=search_fn
    def search(self,query:str,k:int=5):
        if not query.strip(): raise ValueError('query must be non-empty')
        if k<1: raise ValueError('k must be positive')
        rows=list(self.search_fn(query,int(k)))
        if not rows:return []
        if all(isinstance(x,KnowledgeDocument) for x in rows):
            return InMemoryKnowledgeStore(rows,chunk_chars=800).search(query,k=min(k,len(rows)))
        if all(isinstance(x,EvidenceChunk) for x in rows):
            for x in rows:
                if hashlib.sha256(x.text.encode()).hexdigest()!=x.content_sha256: raise ValueError('callback returned tampered evidence')
            return sorted(rows,key=lambda x:(-x.score,-x.trust_score,x.chunk_id))[:k]
        raise TypeError('callback must return only KnowledgeDocument or only EvidenceChunk rows')

def extract_generic_query_anchors(text:str)->tuple[str,...]:
    """Deterministic optional anchor hints for arbitrary prose; not part of locked KFIGG-21 evidence."""
    stop={'The','This','That','These','Those','Where','Which','What','When','Who','How','A','An'}
    return tuple(dict.fromkeys(token for token in re.findall(r'\b[A-Z][A-Za-z0-9_-]{2,}\b',str(text)) if token not in stop))
