from __future__ import annotations
import argparse
from enterprise.illlm_authority import ILLLMAuthority
from deployment import recursive_computer_service_r26 as base
from deployment.recursive_computer_service_r29 import GovernedRuntimeHost


class ILLLMGovernedRuntimeHost(GovernedRuntimeHost):
    def __init__(self, state_root, computer_id="A"):
        super().__init__(state_root, computer_id)
        self.illlm = ILLLMAuthority(self.state_root / "control" / "illlm-execution-ledger.json")

    def illlm_execute(self, request):
        with self._tree_lock:
            return self.illlm.execute(request, self)


class Handler(base.Handler):
    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path != "/v1/illlm/execute":
            return super().do_POST()
        if not self.require_authorized():
            return
        try:
            body = self.body()
            return self.reply(200, self.host_runtime.illlm_execute(body))
        except OverflowError as exc:
            return self.reply(413, {"status": "REJECTED", "reason": str(exc)})
        except (KeyError, ValueError) as exc:
            return self.reply(400, {"status": "REJECTED", "reason": str(exc)})
        except Exception as exc:
            code = 409 if "STALE_STATE_CONFLICT" in str(exc) else 500
            return self.reply(code, {"status": "ERROR", "error": type(exc).__name__ + ":" + str(exc)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--computer-id", default="A")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8811)
    parser.add_argument("--auth-token-file")
    parser.add_argument("--allow-unauthenticated-nonloopback", action="store_true")
    args = parser.parse_args()
    token = base.load_auth_token(args.auth_token_file)
    loopback = {"127.0.0.1", "::1", "localhost"}
    if args.host not in loopback and token is None and not args.allow_unauthenticated_nonloopback:
        raise SystemExit("NON_LOOPBACK_BIND_REQUIRES_AUTH_TOKEN_OR_EXPLICIT_OVERRIDE")
    Handler.host_runtime = ILLLMGovernedRuntimeHost(args.state_root, args.computer_id)
    Handler.auth_token = token
    server = base.RuntimeServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
