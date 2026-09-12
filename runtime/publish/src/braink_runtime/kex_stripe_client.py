from __future__ import annotations
import json
import socket


class KEXStripeError(RuntimeError):
    pass


class KEXStripeClient:
    """Client for the KEX-owned Stripe capability socket.

    The BRAINK/CasePath process never receives Stripe secret material. It sends a
    bounded operation to the resident KEX capability and receives only sanitized
    provider output plus a KEX receipt identifier.
    """

    def __init__(self, socket_path: str = "/run/keddeh/kex-runner.sock", timeout: float = 5.0):
        self.socket_path = socket_path
        self.timeout = timeout

    def call(self, op: str, payload: dict) -> dict:
        request = {"op": op, "payload": payload}
        data = (json.dumps(request, separators=(",", ":")) + "\n").encode("utf-8")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(self.timeout)
            sock.connect(self.socket_path)
            sock.sendall(data)
            chunks: list[bytes] = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                if b"\n" in chunk:
                    break
        if not chunks:
            raise KEXStripeError("empty KEX response")
        response = json.loads(b"".join(chunks).split(b"\n", 1)[0])
        if response.get("status") != "PASS":
            raise KEXStripeError(response.get("error", "KEX Stripe operation failed"))
        return response
