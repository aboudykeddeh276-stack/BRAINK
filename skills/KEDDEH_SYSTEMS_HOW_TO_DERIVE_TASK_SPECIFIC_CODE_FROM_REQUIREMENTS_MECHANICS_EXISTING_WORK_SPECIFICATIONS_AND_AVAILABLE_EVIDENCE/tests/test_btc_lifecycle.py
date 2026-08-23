from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from btc.controller import LiveMinerConfig, run_continuous_miner
from btc.pipeline import PipelineResult

ZERO_HASH = "00" * 32
OTHER_HASH = "11" * 32


def template(height: int = 840000) -> dict:
    return {
        "version": 0x20000000,
        "previousblockhash": ZERO_HASH,
        "bits": "207fffff",
        "curtime": 1700000000,
        "height": height,
        "transactions": [],
    }


def empty_result(worker_count: int = 4, cancelled: bool = False) -> PipelineResult:
    return PipelineResult(
        coinbase_txid_display="",
        merkle_root_internal=bytes(32),
        winning_nonce=None,
        block_hash_display=None,
        block_bytes=None,
        submit_request=None,
        stale=False,
        worker_count=worker_count,
        cancelled=cancelled,
    )


def candidate_result(worker_count: int = 4) -> PipelineResult:
    return PipelineResult(
        coinbase_txid_display="cb",
        merkle_root_internal=bytes(32),
        winning_nonce=7,
        block_hash_display="candidate-hash",
        block_bytes=b"\x00" * 81,
        submit_request={"method": "submitblock"},
        stale=False,
        worker_count=worker_count,
        cancelled=False,
    )


class FakeClient:
    def __init__(self, submit_result=None) -> None:
        self.template_calls = 0
        self.tip_calls = 0
        self.submit_calls = 0
        self.submit_result = submit_result

    def getblockchaininfo(self) -> dict:
        return {"chain": "main", "initialblockdownload": False}

    def getblocktemplate(self, _rules=None) -> dict:
        self.template_calls += 1
        return template(840000 + self.template_calls - 1)

    def getbestblockhash(self) -> str:
        self.tip_calls += 1
        return ZERO_HASH

    def submitblock(self, _block_hex: str):
        self.submit_calls += 1
        return self.submit_result


class BtcLifecycleTests(unittest.TestCase):
    def config(self, **overrides) -> LiveMinerConfig:
        base = dict(
            worker_count=4,
            max_nonce_scan=64,
            stale_poll_seconds=0.005,
            retry_initial_seconds=0.0,
            retry_max_seconds=0.0,
        )
        base.update(overrides)
        return LiveMinerConfig(**base)

    def test_nonce_exhaustion_refreshes_work_and_rolls_extranonce(self) -> None:
        client = FakeClient()
        extranonces = []

        def fake_pipeline(**kwargs):
            extranonces.append(kwargs["extranonce"])
            return empty_result(kwargs["worker_count"])

        with patch("btc.controller.run_pipeline", side_effect=fake_pipeline):
            summary = run_continuous_miner(
                client,
                payout_script=b"\x51",
                config=self.config(),
                max_rounds=2,
            )

        self.assertEqual(summary.rounds, 2)
        self.assertEqual(summary.templates, 2)
        self.assertEqual(summary.nonce_exhaustions, 2)
        self.assertEqual(client.template_calls, 2)
        self.assertEqual(len(extranonces), 2)
        self.assertNotEqual(extranonces[0], extranonces[1])
        self.assertEqual(extranonces[0][-8:], (0).to_bytes(8, "little"))
        self.assertEqual(extranonces[1][-8:], (1).to_bytes(8, "little"))

    def test_candidate_is_rechecked_and_submitted(self) -> None:
        client = FakeClient(submit_result=None)
        with patch("btc.controller.run_pipeline", return_value=candidate_result()):
            summary = run_continuous_miner(
                client,
                payout_script=b"\x51",
                config=self.config(),
                max_rounds=1,
            )

        self.assertEqual(summary.candidates, 1)
        self.assertEqual(summary.submissions, 1)
        self.assertEqual(summary.accepted, 1)
        self.assertEqual(summary.rejected, 0)
        self.assertEqual(client.submit_calls, 1)

    def test_rejected_candidate_reconciles_into_next_round(self) -> None:
        client = FakeClient(submit_result="rejected-for-test")
        with patch("btc.controller.run_pipeline", return_value=candidate_result()):
            summary = run_continuous_miner(
                client,
                payout_script=b"\x51",
                config=self.config(),
                max_rounds=2,
            )

        self.assertEqual(summary.rounds, 2)
        self.assertEqual(summary.submissions, 2)
        self.assertEqual(summary.rejected, 2)
        self.assertEqual(client.template_calls, 2)

    def test_transient_rpc_failure_retries_without_promoting_to_fatal(self) -> None:
        class RetryClient(FakeClient):
            def __init__(self) -> None:
                super().__init__()
                self.info_calls = 0

            def getblockchaininfo(self) -> dict:
                self.info_calls += 1
                if self.info_calls == 1:
                    raise OSError("temporary transport loss")
                return super().getblockchaininfo()

        client = RetryClient()
        with patch("btc.controller.run_pipeline", return_value=empty_result()):
            summary = run_continuous_miner(
                client,
                payout_script=b"\x51",
                config=self.config(),
                max_rounds=1,
            )

        self.assertEqual(summary.transient_errors, 1)
        self.assertEqual(summary.rounds, 1)
        self.assertEqual(client.info_calls, 2)

    def test_stale_tip_cancels_hashing_while_round_is_active(self) -> None:
        class StaleClient(FakeClient):
            def getbestblockhash(self) -> str:
                self.tip_calls += 1
                return ZERO_HASH if self.tip_calls == 1 else OTHER_HASH

        client = StaleClient()

        def wait_for_cancel(**kwargs):
            stop = kwargs["stop_event"]
            deadline = time.monotonic() + 1.0
            while not stop.is_set() and time.monotonic() < deadline:
                time.sleep(0.001)
            self.assertTrue(stop.is_set(), "stale watcher did not cancel active hashing")
            return empty_result(kwargs["worker_count"], cancelled=True)

        with patch("btc.controller.run_pipeline", side_effect=wait_for_cancel):
            summary = run_continuous_miner(
                client,
                payout_script=b"\x51",
                config=self.config(stale_poll_seconds=0.001),
                max_rounds=1,
            )

        self.assertEqual(summary.rounds, 1)
        self.assertEqual(summary.stale_cancellations, 1)
        self.assertEqual(summary.submissions, 0)

    def test_explicit_stop_ends_lifecycle_without_starting_work(self) -> None:
        stop = Event()
        stop.set()
        summary = run_continuous_miner(
            FakeClient(),
            payout_script=b"\x51",
            config=self.config(),
            stop_event=stop,
        )
        self.assertTrue(summary.stopped)
        self.assertEqual(summary.rounds, 0)
        self.assertEqual(summary.templates, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
