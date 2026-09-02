from typing import Iterable,Mapping

def reconcile(process_state:str, observations:Iterable[Mapping], conflicts=()):
    obs=list(observations); conflicts=list(conflicts)
    contradictory=bool(conflicts) or any(str(o.get("status","")).upper()=="CONTRADICTION" for o in obs)
    observed=bool(obs)
    return {
      "process_state":process_state,
      "observer_state":"OBSERVER_CONTRADICTORY" if contradictory else ("OBSERVER_OBSERVED" if observed else "OBSERVER_UNREAD"),
      "reconciliation_state":"RECONCILIATION_REPAIR_REQUIRED" if contradictory else ("RECONCILIATION_ACCEPTED" if process_state in {"PROCESS_EXECUTED","PROCESS_SIGNALED"} else "RECONCILIATION_PENDING"),
    }
