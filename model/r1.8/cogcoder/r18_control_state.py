from __future__ import annotations
import torch
from torch import Tensor

def infer_controllable_effect_projection(previous_ids:Tensor,previous_values:Tensor,current_ids:Tensor,current_values:Tensor,*,role_dim:int=64,source_dim:int=128,change_tolerance:float=1e-6)->dict[str,Tensor]:
    if previous_ids.shape!=current_ids.shape or previous_values.shape!=current_values.shape: raise ValueError('previous/current structured tensors must share shapes')
    if previous_ids.ndim!=3 or previous_ids.shape[-1]!=5: raise ValueError('structured ids must have shape [batch,atoms,5]')
    if previous_values.ndim!=3 or previous_values.shape[-1]!=4: raise ValueError('structured values must have shape [batch,atoms,4]')
    batch=previous_ids.shape[0];device=current_values.device;dtype=current_values.dtype;projection=torch.zeros(batch,role_dim,source_dim,device=device,dtype=dtype);confidence=torch.zeros(batch,device=device,dtype=dtype);group_size=torch.zeros(batch,device=device,dtype=torch.long)
    for b in range(batch):
        groups={}
        for i in range(current_ids.shape[1]):
            if int(current_ids[b,i,2])!=1 or int(current_ids[b,i,0])==0: continue
            key=(int(current_ids[b,i,0]),int(current_ids[b,i,1]));groups.setdefault(key,[]).append(i)
        changed=[]
        for key,indices in groups.items():
            positions={int(current_ids[b,i,4]) for i in indices}
            if len(indices)<2 or len(positions)<2: continue
            indices=sorted(indices,key=lambda i:int(current_ids[b,i,4]));aligned=True;is_changed=False
            for i in indices:
                same=(int(previous_ids[b,i,0])==int(current_ids[b,i,0]) and int(previous_ids[b,i,1])==int(current_ids[b,i,1]) and int(previous_ids[b,i,2])==1 and int(current_ids[b,i,2])==1 and int(previous_ids[b,i,4])==int(current_ids[b,i,4]))
                if not same: aligned=False;break
                if float((current_values[b,i]-previous_values[b,i]).abs().max())>change_tolerance: is_changed=True
            if aligned and is_changed: changed.append((key,indices))
        if len(changed)!=1: continue
        (path_hash,key_hash),indices=changed[0];group_size[b]=len(indices);confidence[b]=1.0
        for i in indices:
            pos=int(current_ids[b,i,4]);base=(path_hash*131+key_hash*17+pos*97)%source_dim
            for channel in range(4): projection[b,(pos*97+channel*17)%role_dim,(base+channel*31)%source_dim]=1.0
    return {'effect_projection':projection,'confidence':confidence,'current_group_size':group_size}
