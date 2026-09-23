from __future__ import annotations

class RecursiveOperatorEnvironment:
    def __init__(self, observer2, parent_address='braink://runtime/root'):
        self.observer2=observer2; self.parent_address=parent_address
    def enter(self,address):
        if address!='OBSERVER2://ACTIVE': raise KeyError(address)
        d=self.observer2.descriptor()
        d['LINEAGE']={'parent':self.parent_address,'produces':'OBSERVED_STATE'}
        d['PROOF']='fresh sample bound to observer identity + scope + environment'
        return d
