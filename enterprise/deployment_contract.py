from __future__ import annotations
from dataclasses import dataclass

REQUIRED=("build_receipt","test_receipt","artifact_digest","rollback_ref","owner","environment")

@dataclass(frozen=True)
class DeploymentDecision:
    ready:bool
    missing:tuple[str,...]
    reason:str

def qualify_release(manifest:dict)->DeploymentDecision:
    missing=tuple(k for k in REQUIRED if not manifest.get(k))
    if missing: return DeploymentDecision(False,missing,"MISSING_RELEASE_CONTROLS")
    if manifest.get("change_fail_rate",0) > manifest.get("max_change_fail_rate",1.0):
        return DeploymentDecision(False,(),"CHANGE_FAIL_RATE_LIMIT")
    return DeploymentDecision(True,(),"READY")

def dora_event(commit_at,deployed_at,failed=False,recovered_at=None,rework=False):
    lead=max(0,deployed_at-commit_at)
    recovery=None if not failed or recovered_at is None else max(0,recovered_at-deployed_at)
    return {"lead_time_seconds":lead,"failed":bool(failed),"recovery_seconds":recovery,"rework":bool(rework)}
