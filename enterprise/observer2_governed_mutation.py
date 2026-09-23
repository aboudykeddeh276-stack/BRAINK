from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict
from enterprise.observer2_runtime import Observer2Runtime
from enterprise.observer2_environment_federation import Observer2EnvironmentFederation,FileSystemProbe,ProcessProbe,RecursiveComputerProbe

class Observer2GovernedMutation:
    """Outer execution control loop. Observer2 and mirror never receive actuator authority."""
    def __init__(self,node): self.node=node
    def _observer(self,operation):
        return Observer2Runtime(
            'OBSERVER2://BRAINK/R26/'+'/'.join(self.node.identity.lineage),
            {'operation':operation,'lineage':list(self.node.identity.lineage),'environments':['recursive_computer','state_files','process']},
            federation=Observer2EnvironmentFederation([
                RecursiveComputerProbe('recursive_computer',self.node.inspect_committed),
                FileSystemProbe('state_files',self.node.state_root,('computer.json','ledger.json','runtime-checkpoint.json')),
                ProcessProbe(),
            ]),
        )
    @staticmethod
    def _invariants(before,candidate):
        failures=[]
        if candidate.get('constructor')!=before.get('constructor'): failures.append('CONSTRUCTOR_CHANGED')
        if candidate.get('identity')!=before.get('identity'): failures.append('IDENTITY_CHANGED')
        if not isinstance(candidate.get('children'),list): failures.append('CHILDREN_NOT_LIST')
        return failures
    def execute(self,operation,mirror_fn,actuator_fn,expected_fn):
        observer=self._observer(operation)
        pre=observer.sample('PRE_ACTION')
        before=deepcopy(pre.observed_state['federation']['environments']['recursive_computer']['state']['value'])
        candidate=mirror_fn(deepcopy(before))
        failures=self._invariants(before,candidate)
        learning={'admitted':not failures,'failures':failures}
        if failures:
            return {'status':'REJECTED','observer2':{'pre':asdict(pre),'candidate':candidate,'learning':learning,'continuation':'REJECT_CANDIDATE'}}
        result=actuator_fn()
        post=observer.sample('POST_ACTION')
        post_state=post.observed_state['federation']['environments']['recursive_computer']['state']['value']
        comparison=observer.compare(pre,post)
        discrepancy={'resolved':bool(expected_fn(post_state))}
        continuation=observer.update_continuation(discrepancy_post=discrepancy,comparison=comparison,invariants_survived=True)
        return {'status':'EXECUTED','result':result,'observer2':{'pre':asdict(pre),'candidate':candidate,'learning':learning,'post':asdict(post),'comparison':comparison,'discrepancy_post':discrepancy,'continuation':continuation}}
