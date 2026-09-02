from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Dict
import time

@dataclass(frozen=True)
class Carrier:
    carrier_id:str
    priority:int
    available:bool
    route_prefix:str

class ToTOrcDispatcher:
    def __init__(self):
        self.carriers=[Carrier('TL2',10,True,'runtime://braink/active-continuation'),Carrier('TL1',20,True,'runtime://braink/active-continuation'),Carrier('VPN-TL',30,True,'runtime://braink/active-continuation')]
        self.handlers:Dict[str,Callable]={}
        self.receipts=[]
    def set_availability(self,carrier_id,available):
        self.carriers=[Carrier(c.carrier_id,c.priority,available if c.carrier_id==carrier_id else c.available,c.route_prefix) for c in self.carriers]
    def register_handler(self,carrier_id,fn): self.handlers[carrier_id]=fn
    def dispatch(self,continuation:Dict[str,Any])->Dict[str,Any]:
        attempts=[]
        for c in sorted(self.carriers,key=lambda x:x.priority):
            if not c.available:
                attempts.append({'carrier':c.carrier_id,'status':'UNAVAILABLE'}); continue
            fn=self.handlers.get(c.carrier_id)
            if not fn:
                attempts.append({'carrier':c.carrier_id,'status':'NO_HANDLER'}); continue
            out=fn(continuation); attempts.append({'carrier':c.carrier_id,'status':out.get('status'),'result':out})
            if out.get('status') in {'DISPATCHED','ACCEPTED','COMPLETED'}:
                receipt={'status':'DISPATCHED','carrier':c.carrier_id,'route':c.route_prefix,'continuation_id':continuation['continuation_id'],'attempts':attempts,'at_ns':time.time_ns()}
                self.receipts.append(receipt); return receipt
        receipt={'status':'FAILOVER_EXHAUSTED','continuation_id':continuation['continuation_id'],'attempts':attempts,'at_ns':time.time_ns()}
        self.receipts.append(receipt); return receipt
