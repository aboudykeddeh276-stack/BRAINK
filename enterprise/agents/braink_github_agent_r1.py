from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional
import hashlib, json, time

def canon(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"))

def sha(v):
    return hashlib.sha256(canon(v).encode()).hexdigest()

READ_OPS={"discover_repository","search_code","read_file","read_commit","read_branch","inspect_pull_request","observe_ci","read_ci_steps","read_ci_logs","read_ci_artifacts","compare_commits","read_status"}
WRITE_OPS={"create_file","update_file","create_branch","create_pull_request","create_issue","update_issue","mirror_release_metadata"}
DESTRUCTIVE_OPS={"delete_file"}
DENIED_DEFAULT={"force_ref_update"}

@dataclass(frozen=True)
class WorkModule:
    work_module_id:str
    repository:str
    operation:str
    target:str
    instruction:str
    explicit_destructive_authority:bool=False

@dataclass
class AgentReceipt:
    agent_id:str
    author_id:str
    work_module_id:str
    repository:str
    operation:str
    target:str
    classification:str
    mutation_root:Optional[str]
    readback_root:Optional[str]
    observed:bool
    created_ns:int
    receipt_root:str=""
    def finalize(self):
        body=asdict(self).copy(); body.pop("receipt_root",None)
        self.receipt_root=sha(body)
        return self

class BrainkGitHubAgent:
    AGENT_ID="BRAINK_AGENT_GITHUB_R1"
    AUTHOR_ID="AKD"
    AUTHORSHIP_ROOT="enterprise/governance/AKD_AUTHORSHIP_ROOT.json"

    def authorize(self,w:WorkModule)->Dict[str,Any]:
        if w.operation in DENIED_DEFAULT:
            return {"allowed":False,"reason":"DENIED_BY_DEFAULT"}
        if w.operation in DESTRUCTIVE_OPS and not w.explicit_destructive_authority:
            return {"allowed":False,"reason":"EXPLICIT_DESTRUCTIVE_AUTHORITY_REQUIRED"}
        if w.operation in READ_OPS|WRITE_OPS|DESTRUCTIVE_OPS:
            return {"allowed":True,"reason":"WORK_MODULE_AUTHORIZED"}
        return {"allowed":False,"reason":"UNKNOWN_OPERATION"}

    def classify(self,w:WorkModule,mutation:Any=None,readback:Any=None,error:Any=None)->AgentReceipt:
        auth=self.authorize(w)
        if not auth["allowed"] or error is not None:
            cls="FAILED"
        elif w.operation in WRITE_OPS|DESTRUCTIVE_OPS:
            cls="OBSERVED" if readback is not None else "SIGNALED"
        else:
            cls="OBSERVED" if readback is not None else "EXECUTED"
        return AgentReceipt(self.AGENT_ID,self.AUTHOR_ID,w.work_module_id,w.repository,w.operation,w.target,cls,sha(mutation) if mutation is not None else None,sha(readback) if readback is not None else None,readback is not None,time.time_ns()).finalize()

    def promotion_allowed(self,receipt:AgentReceipt)->bool:
        if receipt.operation in WRITE_OPS|DESTRUCTIVE_OPS:
            return receipt.classification=="OBSERVED" and receipt.observed
        return receipt.classification in {"OBSERVED","QUALIFIED"}

    def github_is_runtime_authority(self)->bool:
        return False
