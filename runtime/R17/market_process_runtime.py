from dataclasses import dataclass, asdict
import hashlib, json, time, uuid

def h(v):
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()

@dataclass
class Overhead:
    cpu_ms:int=0
    gpu_ms:int=0
    memory_bytes:int=0
    storage_bytes:int=0
    network_bytes:int=0
    llm_input_tokens:int=0
    llm_output_tokens:int=0
    external_calls:int=0
    human_review_seconds:int=0
    cost_minor:int=0

class ProcessRuntime:
    def __init__(self,contracts):
        self.contracts=contracts["processes"]; self.handlers={}; self.runs={}; self.receipts=[]
    def register(self,stage,fn): self.handlers[stage]=fn
    def start(self,pid,payload,context=None):
        if pid not in self.contracts: return {"status":"UNKNOWN_PROCESS"}
        rid="PROC-"+uuid.uuid4().hex[:12]
        self.runs[rid]={"pid":pid,"payload":payload,"context":context or {},"state":{},"index":0,"status":"RUNNING","overhead":Overhead()}
        return {"status":"STARTED","process_run_id":rid}
    def add_overhead(self,rid,delta):
        o=self.runs[rid]["overhead"]
        for k,v in delta.items(): setattr(o,k,getattr(o,k)+int(v))
    def step(self,rid):
        r=self.runs[rid]; c=self.contracts[r["pid"]]
        if r["status"]!="RUNNING": return {"status":r["status"]}
        stage=c["stages"][r["index"]]; started=time.time_ns()
        fn=self.handlers.get(stage)
        result={"status":"NO_HANDLER"} if not fn else fn({"run_id":rid,"process_id":r["pid"],"stage":stage,"payload":r["payload"],"state":r["state"],"context":r["context"]})
        if result.get("overhead"): self.add_overhead(rid,result["overhead"])
        if result.get("state"): r["state"].update(result["state"])
        ok=result.get("status") in {"OK","COMPLETED","ACCEPTED","COMMITTED","CONTINUE"}
        if ok:
            r["index"]+=1
            r["status"]="COMPLETED" if r["index"]>=len(c["stages"]) else "RUNNING"
        else:
            r["status"]="BLOCKED"
        receipt={"process_run_id":rid,"process_id":r["pid"],"stage":stage,"status":r["status"],"state_root":h(r["state"]),"overhead":asdict(r["overhead"]),"started_ns":started,"finished_ns":time.time_ns()}
        self.receipts.append(receipt)
        return {"status":r["status"],"stage":stage,"result":result,"receipt":receipt}
    def run(self,rid,max_steps=100):
        out=[]
        for _ in range(max_steps):
            x=self.step(rid); out.append(x)
            if x["status"]!="RUNNING": break
        return {"status":self.runs[rid]["status"],"steps":out,"summary":self.summary(rid)}
    def summary(self,rid):
        r=self.runs[rid]
        return {"process_run_id":rid,"process_id":r["pid"],"status":r["status"],"completed_stages":r["index"],"state_root":h(r["state"]),"overhead":asdict(r["overhead"])}
