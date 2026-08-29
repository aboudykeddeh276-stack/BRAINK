#!/usr/bin/env python3
"""
Tests for the BTC live control plane (real mainnet execution boundary).

These tests VERIFY the transport, address, payout, controller, Stratum and
telemetry mechanics against independent oracles (BIP173/BIP350 vectors, a
reference bech32 encoder, direct hashlib computation, and the real Merkle rule).
They do not recreate the mechanics and they never pretend to be a live node:
the RPC transport is exercised with an injected opener, and the controller with a
duck-typed client, so the exact bytes/logic that would hit ``bitcoind`` are tested.

Runnable with:
    python3 -m pytest tests/test_btc_live.py
    python3 tests/test_btc_live.py
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from btc.address import AddressError, address_to_script  # noqa: E402
from btc.controller import (  # noqa: E402
    LiveMinerConfig,
    LiveMinerError,
    run_live_attempt,
)
from btc.merkle import apply_coinbase_branch, coinbase_merkle_branch, merkle_root  # noqa: E402
from btc.payout import payout_script_from_address, payout_script_from_wallet  # noqa: E402
from btc.rpc import CoreRpcClient, CoreRpcConfig, RpcError  # noqa: E402
from btc.serialize import sha256d  # noqa: E402
from btc.stratum import (  # noqa: E402
    ShareSubmission,
    StratumJob,
    build_notify,
    build_submit_response,
    build_subscribe_response,
    parse_submit,
)
from btc.telemetry import (  # noqa: E402
    block_probability_per_hash,
    expected_blocks_per_hour,
    profitability,
)


# --------------------------------------------------------------------------- #
# Independent reference bech32 encoder (BIP173/BIP350) used only as an oracle. #
# --------------------------------------------------------------------------- #
_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32M_CONST = 0x2BC830A3


def _bech32_polymod(values: list[int]) -> int:
    generator = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for value in values:
        top = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ value
        for i in range(5):
            chk ^= generator[i] if ((top >> i) & 1) else 0
    return chk


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _convertbits(data: bytes, frombits: int, tobits: int, pad: bool) -> list[int]:
    acc = 0
    bits = 0
    ret: list[int] = []
    maxv = (1 << tobits) - 1
    for value in data:
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad and bits:
        ret.append((acc << (tobits - bits)) & maxv)
    return ret


def _reference_segwit_encode(hrp: str, witver: int, program: bytes) -> str:
    """Encode a segwit address independently (oracle for the decoder)."""
    data = [witver] + _convertbits(program, 8, 5, True)
    const = _BECH32M_CONST if witver != 0 else 1
    polymod = _bech32_polymod(_hrp_expand(hrp) + data + [0, 0, 0, 0, 0, 0]) ^ const
    checksum = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(_CHARSET[d] for d in data + checksum)


# --------------------------------------------------------------------------- #
# Fake HTTP transport / client for deterministic RPC + controller testing.    #
# --------------------------------------------------------------------------- #
class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


class _FakeOpener:
    """Captures the exact Request object and returns a canned JSON body."""

    def __init__(self, responder) -> None:
        self._responder = responder
        self.requests: list = []

    def open(self, req, timeout=None):  # noqa: ANN001 - urllib signature
        self.requests.append(req)
        return _FakeResponse(self._responder(req))


class _FakeClient:
    """Duck-typed CoreRpcClient for controller tests (no network, no simulation
    of consensus — the real pipeline still does all the mechanical work)."""

    def __init__(
        self,
        *,
        chain: str = "main",
        ibd: bool = False,
        prev: str = "00" * 32,
        tip: str | None = None,
        bits: str = "207fffff",
        height: int = 878_000,
        transactions=None,
        submit_result=None,
    ) -> None:
        self._chain = chain
        self._ibd = ibd
        self._prev = prev
        self._tip = tip if tip is not None else prev
        self._bits = bits
        self._height = height
        self._transactions = transactions or []
        self._submit_result = submit_result
        self.submitted_hex: str | None = None

    def getblockchaininfo(self) -> dict:
        return {"chain": self._chain, "initialblockdownload": self._ibd}

    def getblocktemplate(self, rules) -> dict:  # noqa: ANN001
        return {
            "version": 0x20000000,
            "previousblockhash": self._prev,
            "bits": self._bits,
            "curtime": 1_700_000_000,
            "height": self._height,
            "transactions": self._transactions,
        }

    def getbestblockhash(self) -> str:
        return self._tip

    def submitblock(self, block_hex: str):
        self.submitted_hex = block_hex
        return self._submit_result

    def getnewaddress(self, label: str = "", address_type: str = "bech32") -> str:
        return "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"

    def getaddressinfo(self, address: str) -> dict:
        return {"scriptPubKey": "0014751e76e8199196d454941c45d1b3a323f1433bd6"}


def _userpass_config(**kw) -> CoreRpcConfig:
    params = dict(host="127.0.0.1", rpc_user="u", rpc_password="p")
    params.update(kw)
    return CoreRpcConfig(**params)


class AddressTests(unittest.TestCase):
    def test_bip173_p2wpkh_vector(self) -> None:
        self.assertEqual(
            address_to_script("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4").hex(),
            "0014751e76e8199196d454941c45d1b3a323f1433bd6",
        )

    def test_bip350_p2tr_vector(self) -> None:
        self.assertEqual(
            address_to_script(
                "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0"
            ).hex(),
            "5120" + "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
        )

    def test_p2pkh_base58_vector(self) -> None:
        # scriptPubKey = OP_DUP OP_HASH160 <20B> OP_EQUALVERIFY OP_CHECKSIG
        self.assertEqual(
            address_to_script("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2").hex(),
            "76a914" + "77bff20c60e522dfaa3350c39b030a5d004e839a" + "88ac",
        )

    def test_p2sh_base58_roundtrip(self) -> None:
        # Independent oracle: build a P2SH address from a known hash and decode it.
        script_hash = bytes(range(20))
        payload = b"\x05" + script_hash
        checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
        alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        num = int.from_bytes(payload + checksum, "big")
        enc = ""
        while num:
            num, rem = divmod(num, 58)
            enc = alphabet[rem] + enc
        enc = "1" * (len(payload + checksum) - len((payload + checksum).lstrip(b"\x00"))) + enc
        self.assertEqual(
            address_to_script(enc).hex(), "a914" + script_hash.hex() + "87"
        )

    def test_p2wsh_roundtrip_against_reference_encoder(self) -> None:
        program = bytes(range(32))
        addr = _reference_segwit_encode("bc", 0, program)
        self.assertEqual(address_to_script(addr).hex(), "0020" + program.hex())

    def test_p2tr_roundtrip_against_reference_encoder(self) -> None:
        program = bytes(range(32, 64))
        addr = _reference_segwit_encode("bc", 1, program)
        self.assertEqual(address_to_script(addr).hex(), "5120" + program.hex())

    def test_tampered_checksum_rejected(self) -> None:
        good = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
        with self.assertRaises(AddressError):
            address_to_script(good[:-1] + ("q" if good[-1] != "q" else "p"))

    def test_wrong_network_hrp_rejected(self) -> None:
        # A valid testnet address must not resolve on mainnet.
        testnet = _reference_segwit_encode("tb", 0, bytes(20))
        with self.assertRaises(AddressError):
            address_to_script(testnet)

    def test_v0_program_with_bech32m_is_rejected(self) -> None:
        # v0 must use bech32 (const 1); encoding it as bech32m must fail.
        # Encode v0 but force the bech32m constant to prove the decoder checks it.
        program = bytes(20)
        data = [0] + _convertbits(program, 8, 5, True)
        polymod = _bech32_polymod(_hrp_expand("bc") + data + [0] * 6) ^ _BECH32M_CONST
        checksum = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
        addr = "bc1" + "".join(_CHARSET[d] for d in data + checksum)
        with self.assertRaises(AddressError):
            address_to_script(addr)


class RpcConfigTests(unittest.TestCase):
    def test_private_host_allowed_by_default(self) -> None:
        for host in ("127.0.0.1", "localhost", "10.0.0.5", "192.168.1.2"):
            cfg = _userpass_config(host=host)
            self.assertEqual(cfg.host, host)

    def test_public_host_refused_by_default(self) -> None:
        with self.assertRaises(ValueError):
            _userpass_config(host="8.8.8.8")

    def test_public_host_allowed_with_optin(self) -> None:
        cfg = _userpass_config(host="8.8.8.8", allow_nonlocal=True)
        self.assertTrue(cfg.allow_nonlocal)

    def test_requires_exactly_one_auth_method(self) -> None:
        with self.assertRaises(ValueError):
            CoreRpcConfig(host="127.0.0.1")  # neither
        with self.assertRaises(ValueError):
            CoreRpcConfig(
                host="127.0.0.1", cookie_path="/x/.cookie", rpc_user="u", rpc_password="p"
            )  # both

    def test_port_range_validated(self) -> None:
        with self.assertRaises(ValueError):
            _userpass_config(port=70000)

    def test_auth_header_userpass(self) -> None:
        cfg = _userpass_config(rpc_user="alice", rpc_password="s3cr3t")
        expected = "Basic " + base64.b64encode(b"alice:s3cr3t").decode()
        self.assertEqual(cfg.auth_header_value(), expected)

    def test_auth_header_cookie(self) -> None:
        with _temp_cookie("__cookie__:deadbeef") as cookie_path:
            cfg = CoreRpcConfig(host="127.0.0.1", cookie_path=cookie_path)
            expected = "Basic " + base64.b64encode(b"__cookie__:deadbeef").decode()
            self.assertEqual(cfg.auth_header_value(), expected)

    def test_endpoint_url_wallet_scoping(self) -> None:
        cfg = _userpass_config(wallet="w1")
        self.assertEqual(cfg.endpoint_url(False), "http://127.0.0.1:8332")
        self.assertEqual(cfg.endpoint_url(True), "http://127.0.0.1:8332/wallet/w1")


class RpcClientTransportTests(unittest.TestCase):
    def _client(self, responder):
        opener = _FakeOpener(responder)
        client = CoreRpcClient(_userpass_config(rpc_user="u", rpc_password="p"), opener=opener)
        return client, opener

    def test_call_builds_correct_request_and_returns_result(self) -> None:
        def responder(req) -> bytes:
            return json.dumps({"result": {"chain": "main"}, "error": None, "id": 1}).encode()

        client, opener = self._client(responder)
        result = client.getblockchaininfo()
        self.assertEqual(result, {"chain": "main"})
        sent = opener.requests[0]
        self.assertEqual(sent.method, "POST")
        self.assertEqual(sent.full_url, "http://127.0.0.1:8332")
        body = json.loads(sent.data.decode())
        self.assertEqual(body["method"], "getblockchaininfo")
        self.assertEqual(sent.get_header("Authorization"), cfg_auth("u", "p"))
        self.assertEqual(sent.get_header("Content-type"), "application/json")

    def test_rpc_error_is_raised(self) -> None:
        def responder(req) -> bytes:
            return json.dumps({"result": None, "error": {"code": -8, "message": "boom"}}).encode()

        client, _ = self._client(responder)
        with self.assertRaises(RpcError) as ctx:
            client.getbestblockhash()
        self.assertEqual(ctx.exception.code, -8)

    def test_wallet_scoped_call_uses_wallet_endpoint(self) -> None:
        def responder(req) -> bytes:
            return json.dumps({"result": "bc1qaddr", "error": None}).encode()

        opener = _FakeOpener(responder)
        client = CoreRpcClient(_userpass_config(rpc_user="u", rpc_password="p", wallet="w"), opener=opener)
        client.getnewaddress()
        self.assertEqual(opener.requests[0].full_url, "http://127.0.0.1:8332/wallet/w")

    def test_submitblock_null_result_means_accepted(self) -> None:
        def responder(req) -> bytes:
            return json.dumps({"result": None, "error": None}).encode()

        client, _ = self._client(responder)
        self.assertIsNone(client.submitblock("00"))


class PayoutTests(unittest.TestCase):
    def test_from_address_matches_decoder(self) -> None:
        addr = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
        self.assertEqual(payout_script_from_address(addr), address_to_script(addr))

    def test_from_wallet_prefers_node_scriptpubkey(self) -> None:
        client = _FakeClient()
        address, script = payout_script_from_wallet(client)
        self.assertEqual(address, "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")
        self.assertEqual(script.hex(), "0014751e76e8199196d454941c45d1b3a323f1433bd6")


class ControllerTests(unittest.TestCase):
    _SCRIPT = address_to_script("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")

    def test_full_live_attempt_finds_and_submits_candidate(self) -> None:
        client = _FakeClient()  # easy regtest bits => candidate found deterministically
        attempt = run_live_attempt(
            client, self._SCRIPT, LiveMinerConfig(max_nonce_scan=1 << 16), submit=True
        )
        self.assertTrue(attempt.candidate_found)
        self.assertTrue(attempt.submitted)
        self.assertTrue(attempt.submit_result.accepted)
        self.assertEqual(attempt.pipeline.block_bytes.hex(), client.submitted_hex)

    def test_no_submit_flag_runs_pipeline_without_submitting(self) -> None:
        client = _FakeClient()
        attempt = run_live_attempt(
            client, self._SCRIPT, LiveMinerConfig(max_nonce_scan=1 << 16), submit=False
        )
        self.assertTrue(attempt.candidate_found)
        self.assertFalse(attempt.submitted)
        self.assertIsNone(client.submitted_hex)

    def test_wrong_chain_is_refused(self) -> None:
        client = _FakeClient(chain="test")
        with self.assertRaises(LiveMinerError):
            run_live_attempt(client, self._SCRIPT)

    def test_initial_block_download_is_refused(self) -> None:
        client = _FakeClient(ibd=True)
        with self.assertRaises(LiveMinerError):
            run_live_attempt(client, self._SCRIPT)

    def test_stale_tip_short_circuits_without_submit(self) -> None:
        # Live tip advanced past the template's previous hash -> stale, never submit.
        client = _FakeClient(prev="00" * 32, tip="11" * 32)
        attempt = run_live_attempt(
            client, self._SCRIPT, LiveMinerConfig(max_nonce_scan=1 << 12), submit=True
        )
        self.assertTrue(attempt.stale)
        self.assertFalse(attempt.submitted)
        self.assertIsNone(client.submitted_hex)

    def test_empty_payout_script_is_refused(self) -> None:
        with self.assertRaises(LiveMinerError):
            run_live_attempt(_FakeClient(), b"")


class StratumTests(unittest.TestCase):
    def test_subscribe_response_carries_extranonce_domain(self) -> None:
        resp = build_subscribe_response(7, "abcd1234", 4)
        self.assertEqual(resp["id"], 7)
        self.assertEqual(resp["result"][1], "abcd1234")
        self.assertEqual(resp["result"][2], 4)
        self.assertIsNone(resp["error"])

    def test_notify_params_order(self) -> None:
        job = StratumJob(
            job_id="job1",
            prevhash_hex="aa" * 32,
            coinb1_hex="01",
            coinb2_hex="02",
            merkle_branch_hex=["bb" * 32],
            version_hex="20000000",
            nbits_hex="207fffff",
            ntime_hex="65500000",
            clean_jobs=True,
        )
        params = build_notify(job)["params"]
        self.assertEqual(params[0], "job1")
        self.assertEqual(params[2], "01")
        self.assertEqual(params[3], "02")
        self.assertEqual(params[-1], True)

    def test_parse_submit_roundtrip(self) -> None:
        message = {
            "id": 4,
            "method": "mining.submit",
            "params": ["worker.1", "job1", "00000001", "65500000", "deadbeef"],
        }
        share = parse_submit(message)
        self.assertIsInstance(share, ShareSubmission)
        self.assertEqual(share.worker_name, "worker.1")
        self.assertEqual(share.nonce_hex, "deadbeef")
        self.assertIsNone(share.version_bits_hex)

    def test_parse_submit_rejects_wrong_method(self) -> None:
        with self.assertRaises(ValueError):
            parse_submit({"method": "mining.authorize", "params": []})

    def test_submit_response_accept_and_reject(self) -> None:
        self.assertTrue(build_submit_response(1, True)["result"])
        rejected = build_submit_response(1, False, "stale")
        self.assertFalse(rejected["result"])
        self.assertEqual(rejected["error"][1], "stale")

    def test_merkle_branch_folds_to_real_root(self) -> None:
        # Independent oracle: the real Merkle rule over [coinbase] + others must
        # equal folding the coinbase through the Stratum branch.
        coinbase = sha256d(b"coinbase")
        others = [sha256d(f"tx{i}".encode()) for i in range(4)]
        branch = coinbase_merkle_branch(others)
        folded = apply_coinbase_branch(coinbase, branch)
        self.assertEqual(folded, merkle_root([coinbase] + others))

    def test_merkle_branch_single_and_odd_counts(self) -> None:
        coinbase = sha256d(b"cb")
        for count in (0, 1, 2, 3, 5):
            others = [sha256d(f"o{i}".encode()) for i in range(count)]
            branch = coinbase_merkle_branch(others)
            self.assertEqual(
                apply_coinbase_branch(coinbase, branch), merkle_root([coinbase] + others)
            )


class TelemetryTests(unittest.TestCase):
    def test_block_probability_is_target_over_hash_space(self) -> None:
        bits = 0x1D00FFFF
        from btc.target import bits_to_target

        self.assertEqual(block_probability_per_hash(bits), bits_to_target(bits) / (1 << 256))

    def test_expected_blocks_scales_with_hashrate(self) -> None:
        bits = 0x1D00FFFF
        one = expected_blocks_per_hour(1e12, bits)
        two = expected_blocks_per_hour(2e12, bits)
        self.assertAlmostEqual(two, 2 * one)

    def test_profit_is_revenue_minus_cost_same_unit(self) -> None:
        p = profitability(
            hashes_per_second=1e14,
            bits=0x1D00FFFF,
            height=878_000,
            total_fees=50_000_000,
            power_watts=3000.0,
            electricity_cost_per_kwh=0.10,
            btc_price_fiat=60_000.0,
        )
        self.assertAlmostEqual(p.expected_cost_fiat_per_hour, 0.30)
        self.assertAlmostEqual(
            p.expected_profit_fiat_per_hour,
            p.expected_revenue_fiat_per_hour - p.expected_cost_fiat_per_hour,
        )
        self.assertAlmostEqual(
            p.expected_revenue_fiat_per_hour, p.expected_revenue_btc_per_hour * 60_000.0
        )

    def test_negative_inputs_rejected(self) -> None:
        for kwargs in (
            {"power_watts": -1.0},
            {"electricity_cost_per_kwh": -1.0},
            {"btc_price_fiat": -1.0},
        ):
            base = dict(
                hashes_per_second=1e12,
                bits=0x1D00FFFF,
                height=1,
                total_fees=0,
                power_watts=1.0,
                electricity_cost_per_kwh=0.1,
                btc_price_fiat=1.0,
            )
            base.update(kwargs)
            with self.assertRaises(ValueError):
                profitability(**base)


# --------------------------------------------------------------------------- #
# Small helpers                                                               #
# --------------------------------------------------------------------------- #
import contextlib  # noqa: E402
import tempfile  # noqa: E402


@contextlib.contextmanager
def _temp_cookie(content: str):
    with tempfile.NamedTemporaryFile("w", suffix=".cookie", delete=False) as handle:
        handle.write(content)
        path = handle.name
    try:
        yield path
    finally:
        with contextlib.suppress(OSError):
            Path(path).unlink()


def cfg_auth(user: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


if __name__ == "__main__":
    unittest.main(verbosity=2)
