from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol,Dict,Any
class PaymentProvider(Protocol):
    def authorize(self, amount_minor:int, currency:str, reference:str)->Dict[str,Any]: ...
    def capture(self, authorization_id:str)->Dict[str,Any]: ...
    def refund(self, transaction_id:str, amount_minor:int|None=None)->Dict[str,Any]: ...
    def reconcile(self, transaction_id:str)->Dict[str,Any]: ...
@dataclass(frozen=True)
class PaymentRailBinding:
    provider:str
    state:str
    authenticated:bool
    supports_authorize:bool=False
    supports_capture:bool=False
    supports_refund:bool=False
    supports_reconcile:bool=False
    def qualified(self)->bool:
        return self.state=="BOUND" and self.authenticated and self.supports_authorize and self.supports_capture and self.supports_refund and self.supports_reconcile
UNBOUND=PaymentRailBinding(provider="UNBOUND",state="ADAPTER_IMPLEMENTED_UNBOUND",authenticated=False)
