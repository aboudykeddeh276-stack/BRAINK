"""Mechanic: real Bitcoin Core JSON-RPC transport (private control plane).

This is the ONE authoritative connector to a real ``bitcoind`` node. It performs
genuine JSON-RPC over HTTP against the node's RPC interface and interprets the
response per the Bitcoin Core contract. It does not simulate the node.

Topology doctrine (Bitcoin Core, doc/JSON-RPC-interface.md): the RPC interface
must NOT be exposed to the public Internet — RPC credentials grant significant
control over the node and wallet. Therefore this client is *private by default*:
it refuses to talk to a non-local / non-private host unless the caller explicitly
opts in with ``allow_nonlocal=True`` (for a deliberately secured private network).

Authentication is either the auto-generated cookie file
(``<datadir>/.cookie`` -> ``__cookie__:<hex>``) or an ``rpcuser``/``rpcpassword``
(``rpcauth``) pair. Wallet-scoped calls use the dedicated ``/wallet/<name>``
endpoint so wallet RPC stays scoped and private.
"""

from __future__ import annotations

import base64
import ipaddress
import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_LOOPBACK_NAMES = {"localhost"}


def _is_private_host(host: str) -> bool:
    """True when host is loopback / private / link-local (safe for RPC binding)."""
    h = host.strip()
    if h.lower() in _LOOPBACK_NAMES:
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        # A non-literal hostname: resolve to check. If resolution fails, treat as
        # non-private so the private-by-default guard errs on the side of caution.
        try:
            resolved = socket.gethostbyname(h)
            ip = ipaddress.ip_address(resolved)
        except (OSError, ValueError):
            return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


class RpcError(RuntimeError):
    """A JSON-RPC level error returned by Bitcoin Core (non-null ``error``)."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"RPC error {code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CoreRpcConfig:
    """Connection parameters for a real Bitcoin Core RPC endpoint.

    Exactly one authentication method must be supplied: ``cookie_path`` OR the
    ``rpc_user``/``rpc_password`` pair.
    """

    host: str = "127.0.0.1"
    port: int = 8332            # mainnet RPC (testnet 18332, regtest 18443)
    wallet: str | None = None   # wallet name for /wallet/<name> scoped calls
    cookie_path: str | None = None
    rpc_user: str | None = None
    rpc_password: str | None = None
    timeout_seconds: float = 30.0
    use_https: bool = False     # Core serves plain HTTP on a private interface
    allow_nonlocal: bool = False

    def __post_init__(self) -> None:
        if not 1 <= self.port <= 65535:
            raise ValueError(f"port {self.port} out of range")
        has_cookie = bool(self.cookie_path)
        has_userpass = bool(self.rpc_user) and bool(self.rpc_password)
        if has_cookie == has_userpass:
            raise ValueError(
                "supply exactly one auth method: cookie_path OR rpc_user+rpc_password"
            )
        if not self.allow_nonlocal and not _is_private_host(self.host):
            raise ValueError(
                f"refusing to target non-private RPC host {self.host!r}: Bitcoin Core "
                "RPC must not be exposed publicly. Set allow_nonlocal=True only for a "
                "deliberately secured private network."
            )

    def auth_header_value(self) -> str:
        """HTTP Basic credential derived from cookie file or rpcauth pair."""
        if self.cookie_path:
            token = Path(self.cookie_path).read_text(encoding="utf-8").strip()
            user_pass = token  # cookie file is already "__cookie__:<hex>"
        else:
            user_pass = f"{self.rpc_user}:{self.rpc_password}"
        encoded = base64.b64encode(user_pass.encode("utf-8")).decode("ascii")
        return f"Basic {encoded}"

    def endpoint_url(self, wallet_scoped: bool) -> str:
        scheme = "https" if self.use_https else "http"
        base = f"{scheme}://{self.host}:{self.port}"
        if wallet_scoped and self.wallet is not None:
            return f"{base}/wallet/{self.wallet}"
        return base


class CoreRpcClient:
    """A real JSON-RPC client for Bitcoin Core.

    The HTTP transport is injectable (``opener``) so the exact request that would
    hit a live node can be exercised deterministically in tests without pretending
    to be the node.
    """

    def __init__(self, config: CoreRpcConfig, opener: Any | None = None) -> None:
        self._config = config
        self._opener = opener or urllib.request.build_opener()
        self._request_id = 0

    @property
    def config(self) -> CoreRpcConfig:
        return self._config

    def build_request(self, method: str, params: list[Any], wallet_scoped: bool) -> urllib.request.Request:
        """Construct the exact HTTP JSON-RPC request for a real Core node."""
        self._request_id += 1
        payload = json.dumps(
            {"jsonrpc": "1.0", "id": self._request_id, "method": method, "params": params}
        ).encode("utf-8")
        req = urllib.request.Request(
            self._config.endpoint_url(wallet_scoped), data=payload, method="POST"
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", self._config.auth_header_value())
        return req

    def call(self, method: str, params: list[Any] | None = None, wallet_scoped: bool = False) -> Any:
        """Perform a real RPC call and return the ``result`` (raising ``RpcError``)."""
        req = self.build_request(method, params or [], wallet_scoped)
        try:
            with self._opener.open(req, timeout=self._config.timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:  # Core returns JSON error bodies on 500
            body = exc.read().decode("utf-8") if exc.fp else ""
            if not body:
                raise
        parsed = json.loads(body)
        error = parsed.get("error")
        if error:
            raise RpcError(int(error.get("code", -1)), str(error.get("message", "")))
        return parsed.get("result")

    # ---- typed convenience wrappers (node control plane) -------------------
    def getblockchaininfo(self) -> dict:
        return self.call("getblockchaininfo")

    def getbestblockhash(self) -> str:
        return self.call("getbestblockhash")

    def getblocktemplate(self, rules: list[str] | None = None) -> dict:
        template_request = {"rules": rules or ["segwit"]}
        return self.call("getblocktemplate", [template_request])

    def submitblock(self, block_hex: str) -> Any:
        """Return the raw submitblock result: ``None`` accepted, else reject string."""
        return self.call("submitblock", [block_hex])

    # ---- wallet control plane (kept scoped and private) --------------------
    def getnewaddress(self, label: str = "", address_type: str = "bech32") -> str:
        return self.call("getnewaddress", [label, address_type], wallet_scoped=True)

    def getaddressinfo(self, address: str) -> dict:
        return self.call("getaddressinfo", [address], wallet_scoped=True)
