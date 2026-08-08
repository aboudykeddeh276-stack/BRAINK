#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
sys.path.insert(0, str(RUNTIME))

import btc_consensus as btc


class BitcoinConsensusTests(unittest.TestCase):
    def test_genesis_header_known_answer(self) -> None:
        header = bytes.fromhex(
            "01000000"
            + "00" * 32
            + "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
            + "29ab5f49"
            + "ffff001d"
            + "1dac2b7c"
        )
        self.assertEqual(len(header), 80)
        self.assertEqual(
            btc.dsha256(header)[::-1].hex(),
            "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f",
        )
        self.assertLessEqual(int.from_bytes(btc.dsha256(header), "little"), btc.compact_target("1d00ffff"))

    def test_bip34_height_is_first_coinbase_item(self) -> None:
        encoded = btc.bip34_height(840000)
        self.assertEqual(encoded[0], len(encoded) - 1)
        self.assertEqual(encoded[1:], btc.script_num(840000))

    def test_mainnet_v0_bech32_payout_script(self) -> None:
        # BIP173 valid P2WPKH example.
        script = btc.segwit_scriptpubkey("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kygt080")
        self.assertEqual(script.hex(), "0014751e76e8199196d454941c45d1b3a323f1433bd6")

    def test_merkle_duplicates_odd_leaf(self) -> None:
        a, b, c = (btc.dsha256(x) for x in (b"a", b"b", b"c"))
        expected = btc.dsha256(btc.dsha256(a + b) + btc.dsha256(c + c))
        self.assertEqual(btc.merkle_root_internal([a, b, c]), expected)

    def test_candidate_is_bound_to_coinbase_and_block_body(self) -> None:
        template = {
            "version": 0x20000000,
            "previousblockhash": "11" * 32,
            "bits": "207fffff",
            "curtime": 1700000000,
            "height": 101,
            "coinbasevalue": 5_000_000_000,
            "transactions": [],
        }
        candidate = btc.build_candidate(
            template,
            "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kygt080",
            bytes.fromhex("0102030405060708"),
            nonce=0,
        )
        raw = bytes.fromhex(candidate["block_hex"])
        self.assertGreater(len(raw), 81)
        self.assertEqual(raw[:80].hex(), candidate["header_hex"])
        coinbase_txid_internal = bytes.fromhex(candidate["coinbase_txid"])[::-1]
        self.assertEqual(candidate["merkle_root"], coinbase_txid_internal[::-1].hex())
        self.assertIn(candidate["coinbase_hex"], candidate["block_hex"])

    def test_extranonce_changes_coinbase_merkle_and_header(self) -> None:
        template = {
            "version": 1,
            "previousblockhash": "22" * 32,
            "bits": "207fffff",
            "curtime": 1700000001,
            "height": 102,
            "coinbasevalue": 5_000_000_000,
            "transactions": [],
        }
        address = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kygt080"
        a = btc.build_candidate(template, address, (1).to_bytes(8, "little"), 0)
        b = btc.build_candidate(template, address, (2).to_bytes(8, "little"), 0)
        self.assertNotEqual(a["coinbase_txid"], b["coinbase_txid"])
        self.assertNotEqual(a["merkle_root"], b["merkle_root"])
        self.assertNotEqual(a["header_hex"], b["header_hex"])

    def test_wrong_hrp_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            btc.segwit_scriptpubkey("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kygt080", "tb")


if __name__ == "__main__":
    unittest.main()
