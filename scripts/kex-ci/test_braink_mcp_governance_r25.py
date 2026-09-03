from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def send(proc,payload):
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(json.dumps(payload,separators=(",",":"))+"\n");proc.stdin.flush()
    line=proc.stdout.readline();assert line,"MCP server closed stdout";return json.loads(line)


def main():
    with tempfile.TemporaryDirectory(prefix="braink-r25-") as tmp:
        state=Path(tmp)/"state.json";env=dict(os.environ);env["PYTHONPATH"]=str(ROOT)+os.pathsep+env.get("PYTHONPATH","")
        proc=subprocess.Popen([sys.executable,"-m","enterprise.mcp.server_r25","--state",str(state)],cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            init=send(proc,{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}})
            assert init["result"]["serverInfo"]["name"]=="braink-r25-governed-mcp"
            tools=send(proc,{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
            names={x["name"] for x in tools["result"]["tools"]}
            assert "braink_r25_operate" in names and "braink_r23_operate" not in names
            contracts=send(proc,{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"braink_r25_contracts","arguments":{}}})
            items=contracts["result"]["structuredContent"]["contracts"]
            assert len(items)==10
            by={x["action"]:x for x in items}
            assert by["domain.public_activation.request"]["approval_required"] is True

            base={"work_id":"WORK-R25-001","actor_id":"agent-A","lease_epoch":1,"scopes":["customer:write"]}
            created=send(proc,{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"braink_r25_operate","arguments":{"action":"customer.lifecycle.create","payload":{"file_id":"CF-R25-001","customer_id":"C1","consent":{"privacy":True}},"context":base,"idempotency_key":"create-1"}}})
            out=created["result"]["structuredContent"]
            assert out["status"]=="SUCCEEDED" and out["operation"]["status"]=="EXECUTED"

            replay=send(proc,{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"braink_r25_operate","arguments":{"action":"customer.lifecycle.create","payload":{"file_id":"CF-R25-001","customer_id":"C1","consent":{"privacy":True}},"context":base,"idempotency_key":"create-1"}}})
            assert replay["result"]["structuredContent"]["status"]=="REPLAYED_SUCCESS"

            denied=send(proc,{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"braink_r25_operate","arguments":{"action":"customer.lifecycle.transition","payload":{"file_id":"CF-R25-001","target":"ACTIVE","reason":"x"},"context":{"work_id":"W","actor_id":"bad","lease_epoch":1,"scopes":[]},"idempotency_key":"transition-1"}}})
            assert "MISSING_SCOPES" in denied["error"]["message"]

            approval=send(proc,{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"braink_r25_operate","arguments":{"action":"domain.public_activation.request","payload":{"release_id":"REL-R25","domain":"r25.example.invalid","dns_changes":[],"tls_required":True},"context":{"work_id":"W2","actor_id":"agent-A","lease_epoch":2,"scopes":["domain:activate"]},"idempotency_key":"domain-1"}}})
            assert "APPROVAL_REQUIRED" in approval["error"]["message"]

            approved=send(proc,{"jsonrpc":"2.0","id":8,"method":"tools/call","params":{"name":"braink_r25_operate","arguments":{"action":"domain.public_activation.request","payload":{"release_id":"REL-R25","domain":"r25.example.invalid","dns_changes":[],"tls_required":True},"context":{"work_id":"W2","actor_id":"agent-A","lease_epoch":2,"scopes":["domain:activate"],"approval_token":"approval://r25"},"idempotency_key":"domain-1"}}})
            a=approved["result"]["structuredContent"]
            assert a["status"]=="SUCCEEDED" and a["operation"]["status"]=="DEFERRED_EXTERNAL_ACTUATOR"

            conflict=send(proc,{"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"braink_r25_operate","arguments":{"action":"customer.lifecycle.create","payload":{"file_id":"CF-OTHER","customer_id":"C2","consent":{}},"context":base,"idempotency_key":"create-1"}}})
            assert "IDEMPOTENCY_CONFLICT" in conflict["error"]["message"]
        finally:
            proc.terminate();proc.wait(timeout=5)
    print("R25_BRAINK_MCP_GOVERNANCE_PASS")

if __name__=="__main__":main()
