from __future__ import annotations
import hashlib,re
from dataclasses import dataclass
from collections import defaultdict
from .knowledge_types import EvidenceChunk
_CLAIM=re.compile(r'^\s*(.+?)\s+--([^>-]+)-->\s+(.+?)\s*$')
@dataclass(frozen=True)
class Conflict:
    subject:str; relation:str; objects:tuple[str,...]; chunk_ids:tuple[str,...]
class EvidenceLedger:
    def __init__(self): self._chunks={}; self._claims=defaultdict(list); self._order=[]
    def __len__(self): return len(self._chunks)
    def ingest(self,chunk:EvidenceChunk)->bool:
        if hashlib.sha256(chunk.text.encode()).hexdigest()!=chunk.content_sha256: raise ValueError('evidence content hash mismatch')
        if chunk.chunk_id in self._chunks:
            if self._chunks[chunk.chunk_id] != chunk: raise ValueError('chunk id collision')
            return False
        self._chunks[chunk.chunk_id]=chunk; self._order.append(chunk.chunk_id)
        m=_CLAIM.match(chunk.text.strip())
        if m:
            key=(m.group(1).strip(),m.group(2).strip()); self._claims[key].append((m.group(3).strip(),chunk.chunk_id))
        return True
    def verify(self)->bool:
        return all(hashlib.sha256(c.text.encode()).hexdigest()==c.content_sha256 for c in self._chunks.values())
    def conflicts(self):
        out=[]
        for (s,r),vals in sorted(self._claims.items()):
            objs=tuple(dict.fromkeys(v[0] for v in vals))
            if len(objs)>1: out.append(Conflict(s,r,objs,tuple(v[1] for v in vals)))
        return out
    def working_set(self,*,max_chunks:int=8,max_chars:int=6000):
        if max_chunks<1 or max_chars<1: return []
        rows=sorted(self._chunks.values(),key=lambda c:(-(c.score*c.trust_score),-c.trust_score,-c.score,c.chunk_id))
        out=[]; chars=0
        for c in rows:
            if len(out)>=max_chunks: break
            if chars+len(c.text)>max_chars: continue
            out.append(c); chars += len(c.text)
        return out
    def chunks(self): return tuple(self._chunks[cid] for cid in self._order)
