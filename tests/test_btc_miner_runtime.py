#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
sys.path.insert(0, str(RUNTIME))

import btc_miner_runtime as miner

VALID_BIP173 = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"


def template(bits: str = "1d00ffff") -> dict:
    return {
        "version": 0x20000000,
        "previousblockhash": "11" * 32,
        "bits": bits,
        "curtime": 1700000000,
        "height": 101,
        "coinbasevalue": 5_000_000_000,
        "transactions": [],
    }


class BitcoinMinerRuntimeTests(unittest.TestCase):
    def test_core_chain_names_match_getblockchaininfo_contract(self) -> None:
        self.assertEqual(miner.core_chain_name("mainnet"), "main")
        self.assertEqual(miner.core_chain_name("testnet"), "test")
        self.assertEqual(miner.core_chain_name("signet"), "signet")
        self.assertEqual(miner.core_chain_name("regtest"), "regtest")

    def test_unknown_network_is_rejected_before_rpc(self) -> None:
        with patch.dict(os.environ, {"BTC_NETWORK": "unknown", "BTC_PAYOUT_ADDRESS": VALID_BIP173}, clear=False):
            with patch.object(miner, "check_rpc") as check_rpc:
                result = miner.execute()
        self.assertEqual(result["state"], "CONFIGURATION_BLOCKED")
        check_rpc.assert_not_called()

    def test_nonce_scan_assembles_full_block_only_after_target_hit(self) -> None:
        work_template = template()
        prepared = miner.prepare_work(work_template, VALID_BIP173, (1).to_bytes(8, "little"), "mainnet")
        with patch.object(miner, "dsha256", side_effect=[b"\xff" * 32, b"\x00" * 32]):
            with patch.object(miner, "assemble_block", return_value=b"\x01" * 100) as assemble:
                candidate, best, hashes_tested = miner.scan_prepared_work(work_template, prepared, 100)
        self.assertIsNotNone(candidate)
        self.assertEqual(hashes_tested, 2)
        self.assertEqual(candidate["nonce"], 1)
        self.assertTrue(candidate["target_valid"])
        self.assertEqual(candidate["construction_mode"], "PREPARED_INVARIANTS_HEADER_SCAN_ASSEMBLE_ON_HIT")
        self.assertEqual(best["hash_integer"], 0)
        assemble.assert_called_once()

    def test_exhausted_nonce_scan_never_assembles_full_block(self) -> None:
        work_template = template()
        prepared = miner.prepare_work(work_template, VALID_BIP173, (2).to_bytes(8, "little"), "mainnet")
        with patch.object(miner, "dsha256", return_value=b"\xff" * 32):
            with patch.object(miner, "assemble_block") as assemble:
                candidate, best, hashes_tested = miner.scan_prepared_work(work_template, prepared, 3)
        self.assertIsNone(candidate)
        self.assertEqual(hashes_tested, 3)
        self.assertEqual(best["nonce"], 0)
        assemble.assert_not_called()


if __name__ == "__main__":
    unittest.main()
