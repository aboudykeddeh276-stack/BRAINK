#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import ipaddress
import json
import os
import socket
import struct
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

MAINNET_MAGIC = b"\xf9\xbe\xb4\xd9"
MAX_COMMAND_BYTES = 12
MAX_PAYLOAD_BYTES = 32 * 1024 * 1024
DEFAULT_PROTOCOL_VERSION = 70015
NODE_NETWORK = 1


@dataclass(frozen=True)
class OrderBookSnapshot:
    venue_id: str
    target_coin: str
    best_bid_price: float
    best_bid_volume: float
    best_ask_price: float
    best_ask_volume: float
    timestamp: float

    def validate(self) -> None:
        if self.best_bid_price <= 0 or self.best_ask_price <= 0:
            raise ValueError("prices must be positive")
        if self.best_bid_volume < 0 or self.best_ask_volume < 0:
            raise ValueError("volumes cannot be negative")
        if self.best_bid_price > self.best_ask_price:
            raise ValueError("crossed book supplied; use exchange-specific handler before analysis")


@dataclass(frozen=True)
class RouterReceipt:
    receipt_id: str
    mode: str
    p2p_message_bytes: int
    p2p_message_hash: str
    rpc_enabled: bool
    rpc_method: Optional[str]
    rpc_result_present: bool
    arbitrage_simulation_only: bool
    simulated_opportunity: Optional[Dict[str, Any]]
    ledger_path: str
    outbox_manifest: str
    timestamp: float


class NonZeroNetworkSpectra:
    AXIS_MAPPING = [-3, -2, -1, 1, 2, 3]

    @staticmethod
    def resolve_port_offset(logical_index: int) -> int:
        if logical_index == 0:
            raise ArithmeticError("zero is not a valid logical routing index")
        if logical_index not in NonZeroNetworkSpectra.AXIS_MAPPING:
            raise IndexError("logical index outside valid routing axes")
        return 4000 + (logical_index + 3 if logical_index < 0 else logical_index + 2)


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def compact_size(n: int) -> bytes:
    if n < 0:
        raise ValueError("compact_size cannot encode negative values")
    if n < 253:
        return struct.pack("<B", n)
    if n <= 0xFFFF:
        return b"\xfd" + struct.pack("<H", n)
    if n <= 0xFFFFFFFF:
        return b"\xfe" + struct.pack("<I", n)
    if n <= 0xFFFFFFFFFFFFFFFF:
        return b"\xff" + struct.pack("<Q", n)
    raise ValueError("compact_size integer too large")


def ipv4_mapped_address(host: str) -> bytes:
    ip = ipaddress.ip_address(socket.gethostbyname(host))
    if ip.version != 4:
        raise ValueError("only IPv4 mapped addresses are supported in this bounded router")
    return b"\x00" * 10 + b"\xff\xff" + ip.packed


class BitcoinP2PMessageFactory:
    @staticmethod
    def build_message(command: str, payload: bytes) -> bytes:
        command_bytes = command.encode("ascii")
        if not command_bytes:
            raise ValueError("command cannot be empty")
        if len(command_bytes) > MAX_COMMAND_BYTES:
            raise ValueError("Bitcoin P2P command exceeds 12 bytes")
        if len(payload) > MAX_PAYLOAD_BYTES:
            raise ValueError("payload exceeds bounded router maximum")
        command_padded = command_bytes + (b"\x00" * (MAX_COMMAND_BYTES - len(command_bytes)))
        checksum = sha256d(payload)[:4]
        header = MAINNET_MAGIC + command_padded + struct.pack("<I", len(payload)) + checksum
        return header + payload

    @staticmethod
    def build_version_payload(
        *,
        receiving_host: str = "127.0.0.1",
        receiving_port: int = 8333,
        transmitting_host: str = "127.0.0.1",
        transmitting_port: int = 8333,
        start_height: int = 0,
        user_agent: bytes = b"/HEMOS:bounded-v99/",
        relay: bool = True,
        nonce: Optional[bytes] = None,
        timestamp: Optional[int] = None,
    ) -> bytes:
        if len(user_agent) > 252:
            raise ValueError("user_agent too long for bounded compact-size encoder")
        nonce = nonce if nonce is not None else os.urandom(8)
        if len(nonce) != 8:
            raise ValueError("nonce must be exactly 8 bytes")
        timestamp = int(time.time()) if timestamp is None else int(timestamp)

        payload = struct.pack("<iQq", DEFAULT_PROTOCOL_VERSION, NODE_NETWORK, timestamp)
        payload += struct.pack("<Q16sH", NODE_NETWORK, ipv4_mapped_address(receiving_host), receiving_port)
        payload += struct.pack("<Q16sH", NODE_NETWORK, ipv4_mapped_address(transmitting_host), transmitting_port)
        payload += nonce
        payload += compact_size(len(user_agent)) + user_agent
        payload += struct.pack("<i?", int(start_height), bool(relay))
        return payload


class AtomicJsonlLedger:
    def __init__(self, path: Path):
        self.path = path

    def append(self, entry: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(entry, sort_keys=True) + "\n").encode("utf-8")
        fd = os.open(str(self.path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, encoded)
            os.fsync(fd)
        finally:
            os.close(fd)

    def read(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]


class BitcoinCoreRPCBridge:
    def __init__(self, endpoint: str, rpc_user: Optional[str], rpc_password: Optional[str], timeout: float = 5.0):
        self.endpoint = endpoint
        self.rpc_user = rpc_user
        self.rpc_password = rpc_password
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "BitcoinCoreRPCBridge":
        return cls(
            endpoint=os.environ.get("BITCOIN_RPC_URL", "http://127.0.0.1:8332"),
            rpc_user=os.environ.get("BITCOIN_RPC_USER"),
            rpc_password=os.environ.get("BITCOIN_RPC_PASSWORD"),
            timeout=float(os.environ.get("BITCOIN_RPC_TIMEOUT", "5.0")),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.rpc_user and self.rpc_password)

    def call_blocking(self, method: str, params: Optional[List[Any]] = None) -> Optional[Any]:
        allowed_methods = {"getbestblockhash", "getblockchaininfo", "getblock"}
        if method not in allowed_methods:
            raise ValueError(f"RPC method not allowed by bounded bridge: {method}")
        if not self.enabled:
            return None
        payload = json.dumps({"jsonrpc": "1.0", "id": "hemos_v99_query", "method": method, "params": params or []}).encode("utf-8")
        auth = base64.b64encode(f"{self.rpc_user}:{self.rpc_password}".encode("utf-8")).decode("ascii")
        request = urllib.request.Request(self.endpoint, data=payload, headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8")).get("result")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            return None

    async def call(self, method: str, params: Optional[List[Any]] = None) -> Optional[Any]:
        return await asyncio.to_thread(self.call_blocking, method, params)


class ArbitrageAnalyzer:
    def __init__(self, fee_rate: float = 0.001):
        if fee_rate < 0:
            raise ValueError("fee_rate cannot be negative")
        self.fee_rate = fee_rate

    def analyze(self, a: OrderBookSnapshot, b: OrderBookSnapshot) -> Optional[Dict[str, Any]]:
        a.validate()
        b.validate()
        candidates = [self._route("A_TO_B", buy=a, sell=b), self._route("B_TO_A", buy=b, sell=a)]
        candidates = [candidate for candidate in candidates if candidate["net_spread"] > 0]
        if not candidates:
            return None
        best = max(candidates, key=lambda item: item["estimated_opportunity_usd"])
        best["simulation_only"] = True
        best["real_order_submitted"] = False
        return best

    def _route(self, route: str, buy: OrderBookSnapshot, sell: OrderBookSnapshot) -> Dict[str, Any]:
        gross_spread = sell.best_bid_price - buy.best_ask_price
        fees = (sell.best_bid_price + buy.best_ask_price) * self.fee_rate
        net_spread = gross_spread - fees
        volume = min(buy.best_ask_volume, sell.best_bid_volume)
        return {"route": route, "buy_venue": buy.venue_id, "sell_venue": sell.venue_id, "gross_spread": gross_spread, "fees": fees, "net_spread": net_spread, "volume_considered": volume, "estimated_opportunity_usd": max(0.0, net_spread * volume)}


class HEMOSBitcoinCoreRouter:
    def __init__(self, root: Path, rpc: Optional[BitcoinCoreRPCBridge] = None):
        self.root = root.expanduser().resolve()
        self.evidence_dir = self.root / "evidence"
        self.ledger = AtomicJsonlLedger(self.root / "runtime_volume" / "btc_core_protocol_router.ledger")
        self.outbox_dir = self.root / "runtime_volume" / "outbox" / "btc_core_protocol_router"
        self.rpc = rpc or BitcoinCoreRPCBridge.from_env()
        self.analyzer = ArbitrageAnalyzer()

    async def run_once(self, emit_receipt: bool = False) -> RouterReceipt:
        version_payload = BitcoinP2PMessageFactory.build_version_payload(start_height=0, nonce=b"KEDDEH99", timestamp=1700000000)
        wire_message = BitcoinP2PMessageFactory.build_message("version", version_payload)
        p2p_hash = hashlib.sha256(wire_message).hexdigest()
        rpc_result = await self.rpc.call("getbestblockhash") if self.rpc.enabled else None
        rpc_method = "getbestblockhash" if self.rpc.enabled else None
        ts = time.time()
        opportunity = self.analyzer.analyze(
            OrderBookSnapshot("SIM_A", "BTC", 68000.0, 2.5, 68001.0, 1.8, ts),
            OrderBookSnapshot("SIM_B", "BTC", 68015.5, 3.0, 68016.5, 2.2, ts),
        )
        pre_receipt = {"mode": "bounded_local_router", "p2p_message_bytes": len(wire_message), "p2p_message_hash": p2p_hash, "rpc_enabled": self.rpc.enabled, "rpc_method": rpc_method, "rpc_result_present": rpc_result is not None, "arbitrage_simulation_only": True, "simulated_opportunity": opportunity, "timestamp": ts}
        receipt_id = hashlib.sha256(json.dumps(pre_receipt, sort_keys=True).encode("utf-8")).hexdigest()
        receipt_path = self.evidence_dir / "btc_core_protocol_router_receipt.json"
        outbox_path = self.outbox_dir / f"{receipt_id}.handoff.json"
        outbox_path.parent.mkdir(parents=True, exist_ok=True)
        handoff = {"handoff_id": receipt_id, "source": "KEDDEH_V99_BTC_CORE_PROTOCOL_ROUTER", "payload_path": str(receipt_path), "receipt_path": str(self.ledger.path), "next_target": "self_hosted_macos_arm64_runner_with_optional_bitcoind", "status": "READY_FOR_TARGET_HOST_EXECUTION", "created_at": ts}
        outbox_path.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        receipt = RouterReceipt(receipt_id=receipt_id, mode="bounded_local_router", p2p_message_bytes=len(wire_message), p2p_message_hash=p2p_hash, rpc_enabled=self.rpc.enabled, rpc_method=rpc_method, rpc_result_present=rpc_result is not None, arbitrage_simulation_only=True, simulated_opportunity=opportunity, ledger_path=str(self.ledger.path), outbox_manifest=str(outbox_path), timestamp=ts)
        self.ledger.append({"type": "btc_core_protocol_router", "entry_hash": receipt_id, "receipt": asdict(receipt)})
        if emit_receipt:
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return receipt


async def async_main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    receipt = await HEMOSBitcoinCoreRouter(Path(args.root)).run_once(emit_receipt=args.emit_receipt)
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
