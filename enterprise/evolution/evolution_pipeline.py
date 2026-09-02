from pathlib import Path
from .discovery_audit import DiscoveryAuditor
from .deterministic_ledger import ImmutableLedger
from .reconciliation import StateReconciler
from .checkpoint_supervisor import CheckpointSupervisor
from .market_validation import MarketValidator

class EvolutionPipeline:
    def __init__(self,state_dir):
        self.state=Path(state_dir).resolve(); self.state.mkdir(parents=True,exist_ok=True)
        self.ledger=ImmutableLedger(self.state/"EVOLUTION_LEDGER.jsonl")
        self.checkpoints=CheckpointSupervisor(self.state/"CHECKPOINT.json")
    def execute(self,source_tree,declared,observed,market_modules):
        audit=DiscoveryAuditor().audit_tree(source_tree)
        self.ledger.append("DISCOVERY_AUDIT","source_tree",audit,self.state/"DISCOVERY_AUDIT.json")
        rec=StateReconciler().reconcile(declared,observed)
        self.ledger.append("STATE_RECONCILIATION","runtime",rec,self.state/"RECONCILIATION.json")
        mv=MarketValidator(); market=[{**m,"validation":mv.score(m)} for m in market_modules]
        self.ledger.append("MARKET_VALIDATION","services",{"modules":market},self.state/"MARKET_VALIDATION.json")
        cp=self.checkpoints.commit(3,"EXECUTED","CAPABILITY_CLOSURE_AND_DEPLOYMENT",
            {"audit_files":audit["file_count"],"delta_count":len(rec["deltas"]),"market_modules":len(market),"ledger_root":self.ledger.root})
        self.ledger.append("CHECKPOINT","evolution_pipeline",cp,self.state/"CHECKPOINT.json")
        return {"audit":audit,"reconciliation":rec,"market":market,"checkpoint":cp,"ledger_root":self.ledger.root}
