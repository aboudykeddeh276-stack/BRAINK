#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
sys.path.insert(0, str(RUNTIME))

import btc_consensus as btc
import btc_miner_runtime as miner

VALID_BIP173 = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"


def fixture_template() -> dict:
    return {
        "version": 0x20000000,
        "previousblockhash": "11" * 32,
        "bits": "207fffff",
        "curtime": 1700000000,
        "height": 101,
        "coinbasevalue": 5_000_000_000,
        "transactions": [],
    }


class CachedHeaderBitcoinWorkerTests(unittest.TestCase):
    def test_prepared_candidate_is_byte_equivalent_to_reference_constructor(self) -> None:
        template = fixture_template()
        extranonce = bytes.fromhex("0102030405060708")
        work = miner.prepare_nonce_work(template, VALID_BIP173, extranonce, network_hrp_value="bc")
        for nonce in (0, 1, 2, 17, 65535, 0xFFFFFFFF):
            expected = btc.build_candidate(template, VALID_BIP173, extranonce, nonce)
            actual = miner.candidate_from_prepared_work(work, nonce)
            self.assertEqual(actual, expected)

    def test_search_hashes_prepared_header_and_returns_reference_candidate(self) -> None:
        template = fixture_template()
        extranonce = bytes.fromhex("0807060504030201")
        work = miner.prepare_nonce_work(template, VALID_BIP173, extranonce, network_hrp_value="bc")
        result = miner.search_prepared_nonce_work(work, 100)
        self.assertGreaterEqual(result["hashes_tested"], 1)
        self.assertLessEqual(result["hashes_tested"], 100)
        if result["solved"]:
            candidate = result["candidate"]
            reference = btc.build_candidate(template, VALID_BIP173, extranonce, candidate["nonce"])
            self.assertEqual(candidate, reference)
            self.assertTrue(candidate["target_valid"])
        else:
            self.assertIsNone(result["candidate"])
            self.assertIsNotNone(result["best_hash"])

    def test_nonce_bounds_fail_closed(self) -> None:
        template = fixture_template()
        work = miner.prepare_nonce_work(template, VALID_BIP173, b"\x00" * 8, network_hrp_value="bc")
        with self.assertRaises(ValueError):
            miner.candidate_from_prepared_work(work, -1)
        with self.assertRaises(ValueError):
            miner.candidate_from_prepared_work(work, 1 << 32)


if __name__ == "__main__":
    unittest.main()
