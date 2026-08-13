from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class KnowledgeDocument:
    document_id:str
    source_uri:str
    text:str
    version:str='1'
    trust_score:float=1.0
    def __post_init__(self):
        if not self.document_id or not self.source_uri or not self.text.strip(): raise ValueError('document fields must be non-empty')
        if not 0.0 <= float(self.trust_score) <= 1.0: raise ValueError('trust_score must be in [0,1]')

@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id:str; document_id:str; source_uri:str; text:str; content_sha256:str; version:str
    start:int; end:int; score:float; lexical_score:float; semantic_score:float; trust_score:float
