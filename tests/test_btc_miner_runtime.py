#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
import threading
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
                candidate, best, hashes_tested = miner.scan_prepared_work(work_template, prepared, 0, 100)
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
                candidate, best, hashes_tested = miner.scan_prepared_work(work_template, prepared, 7, 3)
        self.assertIsNone(candidate)
        self.assertEqual(hashes_tested, 3)
        self.assertEqual(best["nonce"], 7)
        assemble.assert_not_called()

    def test_allocator_advances_disjoint_windows_for_same_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(miner, "LEDGER_DIR", Path(tmp)):
                first = miner.allocate_work_window(template(), 3)
                second = miner.allocate_work_window(template(), 3)
        self.assertEqual(first["work_key"], second["work_key"])
        self.assertEqual((first["extranonce"], first["nonce_start"], first["nonce_count"]), (0, 0, 3))
        self.assertEqual((second["extranonce"], second["nonce_start"], second["nonce_count"]), (0, 3, 3))

    def test_allocator_rolls_to_next_extranonce_after_uint32_domain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(miner, "LEDGER_DIR", Path(tmp)):
                first = miner.allocate_work_window(template(), miner.UINT32_SPACE)
                second = miner.allocate_work_window(template(), 1)
        self.assertEqual((first["extranonce"], first["nonce_start"], first["nonce_count"]), (0, 0, miner.UINT32_SPACE))
        self.assertEqual((second["extranonce"], second["nonce_start"], second["nonce_count"]), (1, 0, 1))

    def test_allocator_resets_coordinates_for_changed_template_identity(self) -> None:
        changed = template()
        changed["previousblockhash"] = "22" * 32
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(miner, "LEDGER_DIR", Path(tmp)):
                first = miner.allocate_work_window(template(), 5)
                second = miner.allocate_work_window(changed, 5)
        self.assertNotEqual(first["work_key"], second["work_key"])
        self.assertEqual((first["extranonce"], first["nonce_start"]), (0, 0))
        self.assertEqual((second["extranonce"], second["nonce_start"]), (0, 0))

    def test_concurrent_allocator_calls_do_not_overlap(self) -> None:
        allocations = []
        errors = []
        lock = threading.Lock()
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(miner, "LEDGER_DIR", Path(tmp)):
                def allocate() -> None:
                    try:
                        result = miner.allocate_work_window(template(), 10)
                        with lock:
                            allocations.append(result)
                    except Exception as exc:  # pragma: no cover - surfaced by assertion below
                        with lock:
                            errors.append(exc)

                threads = [threading.Thread(target=allocate) for _ in range(12)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(allocations), 12)
        intervals = sorted((item["extranonce"], item["nonce_start"], item["nonce_start"] + item["nonce_count"]) for item in allocations)
        self.assertEqual({item["work_key"] for item in allocations}, {allocations[0]["work_key"]})
        for previous, current in zip(intervals, intervals[1:]):
            self.assertTrue(
                previous[0] < current[0]
                or (previous[0] == current[0] and previous[2] <= current[1]),
                (previous, current),
            )

    def test_explicit_allocation_is_classified_operator_managed(self) -> None:
        with patch.dict(
            os.environ,
            {
                "KEX_WORK_ALLOCATION_MODE": "explicit",
                "KEX_EXTRANONCE": "9",
                "KEX_NONCE_START": "25",
            },
            clear=False,
        ):
            allocation = miner.resolve_work_allocation(template(), 50)
        self.assertEqual(allocation["mode"], "EXPLICIT_OPERATOR_MANAGED")
        self.assertEqual(allocation["extranonce"], 9)
        self.assertEqual(allocation["nonce_start"], 25)
        self.assertEqual(allocation["nonce_count"], 50)


if __name__ == "__main__":
    unittest.main()
