from __future__ import annotations

import argparse
import os
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from deployment.kex_runtime_service_r35 import Handler as R35Handler
from deployment.recursive_computer_service_r26 import RuntimeServer
from deployment.recursive_computer_service_r29 import GovernedRuntimeHost
from deployment.independent_fabric_node_r38 import IndependentFabricNode
from enterprise.canonical_execution_r40 import CanonicalExecutionR40
from enterprise.fabric_admission_r40 import FabricAdmissionR40
from enterprise.illlm_authority import ILLLMAuthority
from enterprise.system_contract_registry import SystemContractRegistry


class CanonicalRuntimeHost(GovernedRuntimeHost):
    def __init__(self, state_root, computer_id="A", advertised_endpoint=None):
        super().__init__(state_root, computer_id)
        self.state_root = Path(state_root)
        self.started_endpoint = advertised_endpoint
        graph_path = Path(__file__).resolve().parents[1] / "control" / "SYSTEM_INTERFACE_GRAPH_R35.json"
        self.system_contracts = SystemContractRegistry(graph_path)
        self.illlm = ILLLMAuthority(self.state_root / "control" / "illlm-execution-ledger-r40.json")
        self.fabric_node = IndependentFabricNode(
            node_id=f"{computer_id}-FABRIC",
            state_root=self.state_root / "fabric-r40",
            advertised_endpoint=advertised_endpoint,
        )
        self.fabric_admission = FabricAdmissionR40(self.fabric_node)
        self.canonical = CanonicalExecutionR40(self, self.state_root, self.fabric_admission)

    def health(self):
        snap = self.snapshot()
        return {
            "status": "LIVE",
            "runtime": "KEDDEH-KEX-R40",
            "computer_id": snap["computer_id"],
            "ledger_verified": snap["ledger_verified"],
            "fabric_node_id": self.fabric_node.node_id,
        }

    def ready(self):
        try:
            snap = self.snapshot()
            contracts = self.system_contracts.verify()
            fabric = self.fabric_node.identity()
            ready = bool(snap["ledger_verified"] and contracts["status"] == "VERIFIED" and fabric["ledger_verified"])
            return {
                "status": "READY" if ready else "NOT_READY",
                "ledger_verified": snap["ledger_verified"],
                "fabric_ledger_verified": fabric["ledger_verified"],
                "system_graph_verified": contracts["status"] == "VERIFIED",
                "component_count": contracts["component_count"],
            }
        except Exception as exc:
            return {"status": "NOT_READY", "error": type(exc).__name__ + ":" + str(exc)}

    def illlm_execute(self, request):
        return self.illlm.execute(request, self)

    def canonical_execute(self, command):
        command = dict(command)
        if command.get("subscriptions") is None and command.get("data_class"):
            command["subscriptions"] = [str(command["data_class"]).upper()]
        if command.get("server_registration") is None and self.started_endpoint:
            command["server_registration"] = {
                "server_id": f"server://kex/{self.computer.identity.computer_id}/r40",
                "endpoint": self.started_endpoint,
                "capabilities": ["CANONICAL_EXECUTION", "IL_LLM", "OBSERVER2", "READBACK"],
                "health": "READY" if self.ready().get("status") == "READY" else "NOT_READY",
            }
        return self.canonical.execute(command)


class Handler(R35Handler):
    server_version = "KEDDEH-KEX-RUNTIME/R40"

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/v1/canonical/status":
            if not self._authorized(path):
                return self._json(401, {"status": "UNAUTHORIZED"})
            return self._json(200, {
                "status": "READ",
                "runtime": self.host_runtime.ready(),
                "global_illlm": self.host_runtime.canonical.global_knowledge.snapshot(),
                "scheduler": self.host_runtime.canonical.scheduler.snapshot(),
                "fabric": self.host_runtime.fabric_node.identity(),
            })
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/v1/canonical/execute":
            if not self._authorized(path):
                return self._json(401, {"status": "UNAUTHORIZED"})
            try:
                body = self._body()
                result = self.host_runtime.canonical_execute(body)
                status = str(result.get("status", ""))
                code = 409 if status.startswith("BLOCKED:") else 200
                return self._json(code, result)
            except (KeyError, ValueError) as exc:
                return self._json(400, {"status": "BLOCKED:INVALID_COMMAND", "reason": str(exc)})
            except Exception as exc:
                return self._json(500, {"status": "FAILED:CANONICAL_EXECUTION", "error": type(exc).__name__ + ":" + str(exc)})
        return super().do_POST()


def build_server(state_root, computer_id="A", host="127.0.0.1", port=8811, auth_token=None, advertised_endpoint=None):
    Handler.host_runtime = CanonicalRuntimeHost(state_root, computer_id, advertised_endpoint=advertised_endpoint)
    Handler.auth_token = auth_token
    return RuntimeServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--computer-id", default="A")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8811)
    parser.add_argument("--auth-token-env", default="KEX_AUTH_TOKEN")
    parser.add_argument("--advertised-endpoint", default=os.environ.get("BRAINK_ADVERTISED_ENDPOINT"))
    args = parser.parse_args()
    token = os.environ.get(args.auth_token_env)
    if args.host not in {"127.0.0.1", "::1", "localhost"} and not token:
        raise SystemExit("NON_LOOPBACK_BIND_REQUIRES_AUTH_TOKEN")
    server = build_server(args.state_root, args.computer_id, args.host, args.port, token, args.advertised_endpoint)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
