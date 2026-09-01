from dataclasses import dataclass

@dataclass(frozen=True)
class Lease:
    epoch:int
    owner:str
    nonce:str

class SimulatedAuthority:
    """Deterministic state-machine model only; not a multi-host implementation."""
    def __init__(self):
        self.epoch=0
        self.current=None
        self.value=None
    def acquire(self,owner,nonce):
        self.epoch+=1
        self.current=Lease(self.epoch,owner,nonce)
        return self.current
    def write(self,lease,value):
        if lease != self.current:
            return "FENCED"
        self.value=(lease.epoch,value)
        return "COMMITTED"

def partition_model():
    a=SimulatedAuthority()
    l1=a.acquire("A","n1")
    l2=a.acquire("B","n2")
    return {
        "stale_A":a.write(l1,"bad"),
        "current_B":a.write(l2,"good"),
        "final":a.value,
        "classification":"STATE_MACHINE_SPECIFICATION_ONLY"
    }
