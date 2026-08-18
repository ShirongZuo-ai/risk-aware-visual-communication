"""Interpretable matched-cost policies for M9 Track-B engineering studies."""
from __future__ import annotations
from dataclasses import dataclass
import math

LOW_BYTES=1500; MEDIUM_BYTES=2000; HIGH_BYTES=3500

@dataclass(frozen=True)
class Allocation:
    method:str
    bytes_per_frame:tuple[int,...]
    risk_scores:tuple[float,...]
    def __post_init__(self):
        if len(self.bytes_per_frame)!=len(self.risk_scores) or not self.bytes_per_frame: raise ValueError("invalid allocation")
        if any(x not in (LOW_BYTES,MEDIUM_BYTES,HIGH_BYTES) for x in self.bytes_per_frame): raise ValueError("unknown frame cost")
    @property
    def total_bytes(self): return sum(self.bytes_per_frame)

def matched_schedule(method:str,risks:list[float],high_frames:int)->Allocation:
    """Exactly match uniform cost: every high frame is funded by three lows."""
    n=len(risks)
    if high_frames<0 or 4*high_frames>n: raise ValueError("high quota cannot be byte matched")
    if method=="U0": return Allocation(method,tuple([MEDIUM_BYTES]*n),tuple(risks))
    # Stable ranking is deterministic and policy-specific; no outcome is used.
    order=sorted(range(n),key=lambda i:(-risks[i],i)); high=set(order[:high_frames]); low=set(order[high_frames:4*high_frames])
    costs=tuple(HIGH_BYTES if i in high else LOW_BYTES if i in low else MEDIUM_BYTES for i in range(n))
    assert sum(costs)==n*MEDIUM_BYTES
    return Allocation(method,costs,tuple(risks))

def matched_causal_schedule(method:str,risks:list[float],high_frames:int)->Allocation:
    """Causal token-bucket policy with exactly matched episode bytes.

    A high frame is allowed only after three low frames bank its 1500-byte
    premium. Unspent credit is deterministically reconciled at episode end.
    """
    if method=="U0": return Allocation(method,tuple([MEDIUM_BYTES]*len(risks)),tuple(risks))
    costs=[];bank=0;used=0
    for risk in risks:
        if risk>=.5 and bank>=1500 and used<high_frames: costs.append(HIGH_BYTES);bank-=1500;used+=1
        elif risk<.5 and used<high_frames: costs.append(LOW_BYTES);bank+=500
        else: costs.append(MEDIUM_BYTES)
    # Exact outcome-independent reconciliation uses last medium/low positions.
    delta=len(costs)*MEDIUM_BYTES-sum(costs)
    for i in range(len(costs)-1,-1,-1):
        if delta==0:break
        if delta>0 and costs[i]==LOW_BYTES:costs[i]=MEDIUM_BYTES;delta-=500
        elif delta<0 and costs[i]==MEDIUM_BYTES:costs[i]=LOW_BYTES;delta+=500
    if delta!=0: raise ValueError("causal policy could not reconcile exact byte budget")
    return Allocation(method,tuple(costs),tuple(risks))

def current_risk(clearance_m:float)->float:
    return 1/(1+math.exp(35*(clearance_m-.04)))

def predictive_risk(clearance_m:float,speed_m_s:float,horizon_s:float=2.0)->float:
    return current_risk(clearance_m-max(0.,speed_m_s)*horizon_s)
