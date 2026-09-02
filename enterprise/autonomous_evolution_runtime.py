from __future__ import annotations
from enterprise.self_addressing_runtime import SelfAddressingRuntime
from enterprise.backing_migration import BackingMigrationCoordinator
from enterprise.observer_policy import ObserverPolicyEngine
from enterprise.mutation_arbiter import MutationArbiter
from enterprise.evolution_paths import EvolutionFabric

class AutonomousEvolutionRuntime(SelfAddressingRuntime):
    def __init__(self,state_path):
        super().__init__(state_path)
        self.evolution=EvolutionFabric()
        self.observer_policy=ObserverPolicyEngine()
        self.migrations=BackingMigrationCoordinator(self.registry,self.binder)
        self.arbiter=MutationArbiter(self.evolution,self.binder,self.observer_policy)
        self.decisions=[]
    def ingest_observer(self, source, subject, kind, payload):
        event=self.observe(source,subject,kind,payload)
        decision=self.observer_policy.as_dict(event)
        self.decisions.append(decision)
        if decision["action"] in {"QUARANTINE_AND_REPAIR","AMEND_OR_REPAIR","DEFER_AND_RESOLVE","RECONCILE"}:
            self.continuations.enqueue(f"KEX://CONTINUATION/{subject}","process://runtime/reconcile",{"subject":subject,"signal":event,"decision":decision},priority=decision["continuation_priority"])
        self.checkpoint()
        return {"event":event,"decision":decision}
    def mutate(self, subject_id, target_address, payload, signals=None):
        out=self.arbiter.dispatch(subject_id,target_address,payload,signals)
        self.checkpoint()
        return out
    def migrate_backing(self, logical, successor_backing):
        out=self.migrations.migrate(logical,successor_backing)
        kind="BACKING_MIGRATION_COMMITTED" if out.get("status")=="COMMITTED" else "BACKING_MIGRATION_FAILED"
        self.ingest_observer("runtime://migration",logical,kind,out)
        self.checkpoint()
        return out
    def snapshot(self):
        base=super().snapshot()
        base.update({"evolution_carrier":self.evolution.carrier,"observer_decisions":self.decisions,"migration_receipts":[r.__dict__ for r in self.migrations.receipts],"arbitrations":[a.__dict__ for a in self.arbiter.history]})
        return base
