#!/usr/bin/env python3
"""
Tests for the canonical BTC mechanics.

These tests VERIFY mechanics; they do not recreate them. Where an expected value
is needed, it comes from an independent oracle (the real Bitcoin genesis block, or
a direct hashlib computation), never by duplicating the system mechanic.

Runnable with:
    python3 -m pytest tests/
    python3 tests/test_btc_mechanics.py
"""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from btc.bip34 import encode_bip34_height  # noqa: E402
from btc.block import assemble_block  # noqa: E402
from btc.coinbase import TxOutput, build_coinbase_tx, coinbase_txid_internal  # noqa: E402
from btc.economics import COIN, block_subsidy, coinbase_value  # noqa: E402
from btc.header import BlockHeader, block_hash_display, block_hash_internal, build_header  # noqa: E402
from btc.merkle import merkle_root  # noqa: E402
from btc.mining import reconstruct_candidate, search_nonce  # noqa: E402
from btc.pipeline import run_pipeline  # noqa: E402
from btc.serialize import compact_size, hash_to_internal, internal_to_display, sha256d  # noqa: E402
from btc.stale import is_stale  # noqa: E402
from btc.submit import build_submitblock_request, interpret_submitblock_response  # noqa: E402
from btc.target import bits_to_target, meets_target  # noqa: E402
from btc.template import BlockTemplate, parse_block_template  # noqa: E402
from btc.witness import witness_commitment_script  # noqa: E402
from btc.work import allocate_work  # noqa: E402

# Independent oracle: the real Bitcoin genesis block.
GENESIS_MERKLE_DISPLAY = "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"
GENESIS_HASH_DISPLAY = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
GENESIS_BITS = 0x1D00FFFF


class SerializeTests(unittest.TestCase):
    def test_sha256d_matches_independent_hashlib(self) -> None:
        data = b"keddeh"
        expected = hashlib.sha256(hashlib.sha256(data).digest()).digest()
        self.assertEqual(sha256d(data), expected)

    def test_compact_size_boundaries(self) -> None:
        self.assertEqual(compact_size(0xFC), b"\xfc")
        self.assertEqual(compact_size(0xFD), b"\xfd\xfd\x00")
        self.assertEqual(compact_size(0x10000), b"\xfe\x00\x00\x01\x00")

    def test_display_internal_roundtrip(self) -> None:
        self.assertEqual(
            internal_to_display(hash_to_internal(GENESIS_HASH_DISPLAY)),
            GENESIS_HASH_DISPLAY,
        )


class HeaderTests(unittest.TestCase):
    def _genesis_header(self) -> bytes:
        return build_header(
            BlockHeader(
                version=1,
                prev_hash_internal=bytes(32),
                merkle_root_internal=hash_to_internal(GENESIS_MERKLE_DISPLAY),
                time=1231006505,
                bits=GENESIS_BITS,
                nonce=2083236893,
            )
        )

    def test_header_is_80_bytes(self) -> None:
        self.assertEqual(len(self._genesis_header()), 80)

    def test_genesis_block_hash_matches_oracle(self) -> None:
        self.assertEqual(block_hash_display(self._genesis_header()), GENESIS_HASH_DISPLAY)

    def test_genesis_meets_its_own_target(self) -> None:
        self.assertTrue(meets_target(block_hash_internal(self._genesis_header()), GENESIS_BITS))


class MerkleTests(unittest.TestCase):
    def test_single_leaf_root_is_that_leaf(self) -> None:
        leaf = hash_to_internal(GENESIS_MERKLE_DISPLAY)
        self.assertEqual(merkle_root([leaf]), leaf)

    def test_two_leaf_root_matches_independent_oracle(self) -> None:
        a = hashlib.sha256(b"a").digest() + hashlib.sha256(b"a").digest()
        a = a[:32]
        b = hashlib.sha256(b"b").digest()
        expected = sha256d(a + b)  # independent direct computation
        self.assertEqual(merkle_root([a, b]), expected)

    def test_odd_row_duplicates_last(self) -> None:
        a = hashlib.sha256(b"a").digest()
        b = hashlib.sha256(b"b").digest()
        c = hashlib.sha256(b"c").digest()
        expected = sha256d(sha256d(a + b) + sha256d(c + c))
        self.assertEqual(merkle_root([a, b, c]), expected)

    def test_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            merkle_root([])


class TargetTests(unittest.TestCase):
    def test_genesis_target_value(self) -> None:
        self.assertEqual(bits_to_target(GENESIS_BITS), 0xFFFF << (8 * (0x1D - 3)))

    def test_low_hash_meets_high_target(self) -> None:
        self.assertTrue(meets_target(bytes(32), GENESIS_BITS))

    def test_max_hash_fails_target(self) -> None:
        self.assertFalse(meets_target(b"\xff" * 32, GENESIS_BITS))


class Bip34Tests(unittest.TestCase):
    def test_height_1(self) -> None:
        self.assertEqual(encode_bip34_height(1), b"\x01\x01")

    def test_height_requires_high_bit_padding(self) -> None:
        # 128 = 0x80 -> needs a trailing 0x00 so it is not read as negative.
        self.assertEqual(encode_bip34_height(128), b"\x02\x80\x00")

    def test_height_multibyte_little_endian(self) -> None:
        # 840000 = 0x0CD140 -> little-endian minimal bytes 40 d1 0c.
        self.assertEqual(encode_bip34_height(840000), b"\x03\x40\xd1\x0c")


class EconomicsTests(unittest.TestCase):
    def test_genesis_subsidy_is_50_btc(self) -> None:
        self.assertEqual(block_subsidy(0), 50 * COIN)

    def test_first_halving(self) -> None:
        self.assertEqual(block_subsidy(210_000), 25 * COIN)

    def test_fourth_halving_height_840000(self) -> None:
        self.assertEqual(block_subsidy(840_000), int(3.125 * COIN))

    def test_subsidy_eventually_zero(self) -> None:
        self.assertEqual(block_subsidy(64 * 210_000), 0)

    def test_coinbase_value_adds_fees(self) -> None:
        self.assertEqual(coinbase_value(0, 1234), 50 * COIN + 1234)


class CoinbaseTests(unittest.TestCase):
    def test_coinbase_scriptsig_starts_with_bip34_height(self) -> None:
        outputs = [TxOutput(50 * COIN, b"\x51")]  # OP_TRUE payout
        tx = build_coinbase_tx(500000, outputs)
        # After version(4) + incount(1) + prevout(32) + index(4) = 41 bytes,
        # a scriptSig length prefix then the BIP34 height push begins.
        script_len = tx[41]
        script = tx[42 : 42 + script_len]
        self.assertTrue(script.startswith(encode_bip34_height(500000)))

    def test_coinbase_txid_is_sha256d_of_serialization(self) -> None:
        outputs = [TxOutput(50 * COIN, b"\x51")]
        tx = build_coinbase_tx(1, outputs)
        self.assertEqual(coinbase_txid_internal(tx), sha256d(tx))


class WitnessTests(unittest.TestCase):
    def test_commitment_script_prefix(self) -> None:
        script = witness_commitment_script([])
        self.assertTrue(script.startswith(bytes.fromhex("6a24aa21a9ed")))
        self.assertEqual(len(script), 6 + 32)

    def test_commitment_matches_independent_computation(self) -> None:
        reserved = b"\x00" * 32
        # Only the coinbase (wtxid all-zero); witness root of a single leaf is the leaf.
        witness_root = b"\x00" * 32
        expected = sha256d(witness_root + reserved)
        script = witness_commitment_script([])
        self.assertEqual(script[6:], expected)


class WorkTests(unittest.TestCase):
    def test_ranges_partition_full_space(self) -> None:
        ranges = allocate_work(7)
        self.assertEqual(ranges[0].nonce_start, 0)
        self.assertEqual(ranges[-1].nonce_end, 1 << 32)
        for a, b in zip(ranges, ranges[1:]):
            self.assertEqual(a.nonce_end, b.nonce_start)  # disjoint & contiguous

    def test_invalid_worker_count(self) -> None:
        with self.assertRaises(ValueError):
            allocate_work(0)


class MiningTests(unittest.TestCase):
    def test_search_and_reconstruct_agree(self) -> None:
        bits = 0x207FFFFF  # easy regtest-style target
        header = build_header(BlockHeader(0x20000000, bytes(32), bytes(32), 1700000000, bits, 0))
        prefix = header[:76]
        nonce = search_nonce(prefix, 0, 1 << 12, bits)
        self.assertIsNotNone(nonce)
        rebuilt = reconstruct_candidate(prefix, nonce)
        self.assertTrue(meets_target(block_hash_internal(rebuilt), bits))


class StaleTests(unittest.TestCase):
    def test_matching_tip_not_stale(self) -> None:
        tip = hash_to_internal(GENESIS_HASH_DISPLAY)
        self.assertFalse(is_stale(tip, tip))

    def test_advanced_tip_is_stale(self) -> None:
        self.assertTrue(is_stale(bytes(32), b"\x01" + bytes(31)))


class SubmitTests(unittest.TestCase):
    def test_request_shape(self) -> None:
        req = build_submitblock_request(b"\xaa\xbb")
        self.assertEqual(req["method"], "submitblock")
        self.assertEqual(req["params"], ["aabb"])

    def test_accepted_response(self) -> None:
        result = interpret_submitblock_response({"result": None, "error": None})
        self.assertTrue(result.accepted)

    def test_rejected_response(self) -> None:
        result = interpret_submitblock_response({"result": "high-hash", "error": None})
        self.assertFalse(result.accepted)
        self.assertEqual(result.reject_reason, "high-hash")

    def test_error_response_raises(self) -> None:
        with self.assertRaises(ValueError):
            interpret_submitblock_response({"error": {"code": -1, "message": "bad"}})


class TemplateTests(unittest.TestCase):
    def test_parse_minimal_template(self) -> None:
        gbt = {
            "version": 0x20000000,
            "previousblockhash": GENESIS_HASH_DISPLAY,
            "bits": "1d00ffff",
            "curtime": 1700000000,
            "height": 840000,
            "transactions": [],
        }
        template = parse_block_template(gbt)
        self.assertEqual(template.height, 840000)
        self.assertEqual(template.bits, GENESIS_BITS)
        self.assertEqual(template.prev_hash_internal, hash_to_internal(GENESIS_HASH_DISPLAY))

    def test_missing_field_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_block_template({"version": 1})


class PipelineCompositionTests(unittest.TestCase):
    """The chain composes the SAME mechanic functions; no logic is re-implemented."""

    def _template(self) -> BlockTemplate:
        return BlockTemplate(
            version=0x20000000,
            prev_hash_internal=bytes(32),
            bits=0x207FFFFF,
            curtime=1700000000,
            height=840000,
            transactions=[],
        )

    def test_full_chain_produces_submittable_block(self) -> None:
        result = run_pipeline(self._template(), payout_script=b"\x51", max_nonce_scan=1 << 16)
        self.assertFalse(result.stale)
        self.assertIsNotNone(result.winning_nonce)
        self.assertIsNotNone(result.block_bytes)
        self.assertEqual(result.submit_request["method"], "submitblock")

    def test_reconstructed_block_hash_meets_target(self) -> None:
        result = run_pipeline(self._template(), payout_script=b"\x51", max_nonce_scan=1 << 16)
        # Independently re-derive the hash from the assembled block's header.
        header = result.block_bytes[:80]
        self.assertEqual(block_hash_display(header), result.block_hash_display)
        self.assertTrue(meets_target(block_hash_internal(header), 0x207FFFFF))

    def test_stale_tip_aborts_before_assembly(self) -> None:
        template = self._template()
        result = run_pipeline(
            template,
            payout_script=b"\x51",
            current_tip_internal=b"\x09" + bytes(31),  # tip advanced
        )
        self.assertTrue(result.stale)
        self.assertIsNone(result.block_bytes)

    def test_assemble_block_places_coinbase_first(self) -> None:
        header = build_header(BlockHeader(1, bytes(32), bytes(32), 1, 0x207FFFFF, 0))
        block = assemble_block(header, b"\xde\xad", [b"\xbe\xef"])
        self.assertEqual(block[:80], header)
        self.assertEqual(block[80], 2)  # compact_size tx count
        self.assertEqual(block[81:83], b"\xde\xad")  # coinbase first


if __name__ == "__main__":
    unittest.main(verbosity=2)
