from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from keddeh_btc_core_protocol_router import (
    BitcoinCoreRPCBridge,
    BitcoinP2PMessageFactory,
    HEMOSBitcoinCoreRouter,
    MAINNET_MAGIC,
    NonZeroNetworkSpectra,
    OrderBookSnapshot,
    network_address,
    sha256d,
)


class BitcoinCoreProtocolRouterTests(unittest.TestCase):
    def test_p2p_message_header_is_24_bytes_and_checksum_matches(self) -> None:
        payload = b"abc"
        message = BitcoinP2PMessageFactory.build_message("version", payload)
        self.assertEqual(message[:4], MAINNET_MAGIC)
        self.assertEqual(message[4:16], b"version" + b"\x00" * 5)
        self.assertEqual(int.from_bytes(message[16:20], "little"), len(payload))
        self.assertEqual(message[20:24], sha256d(payload)[:4])
        self.assertEqual(message[24:], payload)

    def test_version_payload_wraps_as_mainnet_version_message(self) -> None:
        payload = BitcoinP2PMessageFactory.build_version_payload(nonce=b"12345678", timestamp=1700000000)
        message = BitcoinP2PMessageFactory.build_message("version", payload)
        self.assertTrue(message.startswith(MAINNET_MAGIC))
        self.assertEqual(len(message), 24 + len(payload))

    def test_version_network_ports_use_big_endian_wire_order(self) -> None:
        payload = BitcoinP2PMessageFactory.build_version_payload(
            receiving_port=8333,
            transmitting_port=18444,
            nonce=b"12345678",
            timestamp=1700000000,
        )
        # Version/services/timestamp consume 20 bytes. Each network address is
        # 8-byte services + 16-byte IP + 2-byte big-endian port.
        self.assertEqual(payload[44:46], b"\x20\x8d")
        self.assertEqual(int.from_bytes(payload[44:46], "big"), 8333)
        self.assertEqual(int.from_bytes(payload[70:72], "big"), 18444)

    def test_network_address_rejects_invalid_port(self) -> None:
        with self.assertRaises(ValueError):
            network_address(1, "127.0.0.1", 0)
        with self.assertRaises(ValueError):
            network_address(1, "127.0.0.1", 65536)

    def test_rejects_invalid_command_and_zero_index(self) -> None:
        with self.assertRaises(ValueError):
            BitcoinP2PMessageFactory.build_message("this_command_is_too_long", b"")
        with self.assertRaises(ArithmeticError):
            NonZeroNetworkSpectra.resolve_port_offset(0)

    def test_rpc_bridge_disabled_without_credentials(self) -> None:
        bridge = BitcoinCoreRPCBridge("http://127.0.0.1:8332", None, None)
        self.assertFalse(bridge.enabled)
        self.assertIsNone(bridge.call_blocking("getbestblockhash"))

    def test_arbitrage_path_is_simulation_only_not_real_execution(self) -> None:
        from keddeh_btc_core_protocol_router import ArbitrageAnalyzer

        result = ArbitrageAnalyzer().analyze(
            OrderBookSnapshot("A", "BTC", 100.0, 1.0, 101.0, 1.0, 1.0),
            OrderBookSnapshot("B", "BTC", 105.0, 1.0, 106.0, 1.0, 1.0),
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result["simulation_only"])
        self.assertFalse(result["real_order_submitted"])

    def test_router_run_once_writes_receipt_ledger_and_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = asyncio.run(HEMOSBitcoinCoreRouter(root).run_once(emit_receipt=True))
            self.assertGreater(receipt.p2p_message_bytes, 24)
            self.assertTrue(receipt.arbitrage_simulation_only)
            self.assertTrue(Path(receipt.ledger_path).exists())
            self.assertTrue(Path(receipt.outbox_manifest).exists())
            receipt_path = root / "evidence" / "btc_core_protocol_router_receipt.json"
            self.assertTrue(receipt_path.exists())
            data = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(data["receipt_id"], receipt.receipt_id)


if __name__ == "__main__":
    unittest.main()
