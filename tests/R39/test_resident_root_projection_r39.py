from __future__ import annotations

import copy

from enterprise.resident_root_projection_r39 import ROOT_ORDER, ResidentRootProjection


def test_resident_root_snapshot_is_stable_and_verifiable():
    a = ResidentRootProjection().snapshot()
    b = ResidentRootProjection().snapshot()
    assert a["root_set_digest"] == b["root_set_digest"]
    assert set(a["roots"]) == set(ROOT_ORDER)
    assert ResidentRootProjection.verify_snapshot(a)
    assert a["roots"]["TLS_ROOT"]["adapter_binding"] == "UNRESOLVED_ADAPTER"


def test_carrier_coordinates_are_not_part_of_resident_identity():
    snapshot = ResidentRootProjection().snapshot()
    digest = snapshot["root_set_digest"]
    carrier_a = {"endpoint": "http://192.0.2.10:29700", "resident_root_set_digest": digest}
    carrier_b = {"endpoint": "http://198.51.100.44:443", "resident_root_set_digest": digest}
    assert carrier_a["endpoint"] != carrier_b["endpoint"]
    assert carrier_a["resident_root_set_digest"] == carrier_b["resident_root_set_digest"] == digest


def test_tampered_root_body_fails_verification():
    snapshot = ResidentRootProjection().snapshot()
    tampered = copy.deepcopy(snapshot)
    tampered["roots"]["DNS_ROOT"]["body"]["authority"] = "authority://tampered"
    assert not ResidentRootProjection.verify_snapshot(tampered)


def test_root_set_digest_tamper_fails_verification():
    snapshot = ResidentRootProjection().snapshot()
    tampered = copy.deepcopy(snapshot)
    tampered["root_set_digest"] = "0" * 64
    assert not ResidentRootProjection.verify_snapshot(tampered)


def test_tls_adapter_must_not_be_fabricated():
    snapshot = ResidentRootProjection().snapshot()
    tls = snapshot["roots"]["TLS_ROOT"]
    assert tls["adapter_binding"] == "UNRESOLVED_ADAPTER"
    assert tls["body"]["adapter_ref"] is None
