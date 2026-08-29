from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from btc.header import BlockHeader, block_hash_internal, build_header
from btc.mining import search_nonce_concurrent
from btc.pipeline import run_pipeline
from btc.target import meets_target
from btc.template import BlockTemplate
from btc.work import allocate_work_window


class BtcConcurrencyTests(unittest.TestCase):
    def test_bounded_work_ranges_are_disjoint_contiguous_and_complete(self) -> None:
        ranges = allocate_work_window(100, 113, 4)
        self.assertEqual(ranges[0].nonce_start, 100)
        self.assertEqual(ranges[-1].nonce_end, 113)
        self.assertEqual(sum(r.nonce_end - r.nonce_start for r in ranges), 13)
        for left, right in zip(ranges, ranges[1:]):
            self.assertEqual(left.nonce_end, right.nonce_start)

    def test_more_workers_than_nonce_values_does_not_create_empty_lanes(self) -> None:
        ranges = allocate_work_window(7, 10, 20)
        self.assertEqual(len(ranges), 3)
        self.assertTrue(all(r.nonce_end > r.nonce_start for r in ranges))

    def test_concurrent_lanes_use_same_bitcoin_target_predicate(self) -> None:
        bits = 0x207FFFFF
        header = build_header(BlockHeader(0x20000000, bytes(32), bytes(32), 1700000000, bits, 0))
        prefix = header[:76]
        nonce = search_nonce_concurrent(prefix, 0, 1 << 12, bits, worker_count=4)
        self.assertIsNotNone(nonce)
        candidate = prefix + int(nonce).to_bytes(4, "little")
        self.assertTrue(meets_target(block_hash_internal(candidate), bits))

    def test_pipeline_preserves_worker_count_and_builds_valid_candidate(self) -> None:
        template = BlockTemplate(
            version=0x20000000,
            prev_hash_internal=bytes(32),
            bits=0x207FFFFF,
            curtime=1700000000,
            height=840000,
            transactions=[],
        )
        result = run_pipeline(
            template,
            payout_script=b"\x51",
            max_nonce_scan=1 << 12,
            worker_count=4,
        )
        self.assertEqual(result.worker_count, 4)
        self.assertFalse(result.stale)
        self.assertIsNotNone(result.block_bytes)
        self.assertTrue(meets_target(block_hash_internal(result.block_bytes[:80]), template.bits))

    def test_invalid_worker_count_fails_closed(self) -> None:
        template = BlockTemplate(
            version=0x20000000,
            prev_hash_internal=bytes(32),
            bits=0x207FFFFF,
            curtime=1700000000,
            height=840000,
            transactions=[],
        )
        with self.assertRaises(ValueError):
            run_pipeline(template, payout_script=b"\x51", worker_count=0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
