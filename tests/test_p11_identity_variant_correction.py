"""R87 additive P11 carrier-identity collision qualification.

Architect/source authority: A. Keddeh / KS-BRAINK-IL-LLM.
The legacy registry is not rewritten; ambiguous aliases fail closed.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs/estate/P11_IDENTITY_VARIANT_CORRECTION_R87_20261122.json"


def load_manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_retains_architectural_and_source_identity():
    m = load_manifest()
    assert m["architect"] == "A. Keddeh"
    assert m["canonical_architecture"] == "KS-BRAINK-IL-LLM"
    assert m["disposition"] == "PROPOSED_ADDITIVE_CORRECTION_NOT_PROMOTED"
    assert m["source"]["bytes"] == 21_492_468
    assert m["source"]["sha256"] == "e797bc65e71150c300d838616aa39dea7258f53bcd0b77d6c1aa1aad2cc160d9"
    assert m["source"]["raw_registry_rows"] == 98
    assert m["source"]["unique_legacy_carrier_ids"] == 95
    assert m["source"]["logical_objects"] == 76


def test_variant_ids_are_unique_and_content_addressed():
    m = load_manifest()
    ids = [v["variant_id"] for v in m["variants"]]
    hashes = [v["sha256"] for v in m["variants"]]
    assert len(ids) == len(set(ids)) == 6
    assert len(hashes) == len(set(hashes)) == 6
    for v in m["variants"]:
        assert v["variant_id"] == f"{v['legacy_carrier_id_alias']}/sha256/{v['sha256']}"


def test_three_legacy_aliases_fail_closed_and_preserve_both_lifecycle_variants():
    m = load_manifest()
    assert len(m["collisions"]) == 3
    for collision in m["collisions"]:
        assert collision["classification"] == "DUPLICATE_CARRIER_ID_CONTENT_COLLISION"
        assert collision["distinct_sha256"] is True
        assert collision["resolution"] == "legacy alias is ambiguous; resolve only by variant_id or exact SHA-256"
        pair = [v for v in m["variants"] if v["legacy_carrier_id_alias"] == collision["legacy_carrier_id"]]
        assert len(pair) == 2
        assert {v["status"] for v in pair} == {"READY_NEXT", "COMPLETED"}
        assert {v["original_registry_row"] for v in pair} == set(collision["original_rows"])


def test_original_rows_and_logical_identity_are_not_replaced():
    m = load_manifest()
    assert m["identity_policy"]["original_rows_preserved"] is True
    assert m["identity_policy"]["original_carrier_ids_preserved_as_ambiguous_aliases"] is True
    assert m["identity_policy"]["logical_identities_preserved"] is True
    assert m["identity_policy"]["no_source_rewrite"] is True
    assert m["identity_policy"]["no_historical_row_deletion"] is True
    assert m["identity_policy"]["promotion_authorized"] is False
    assert sorted(v["original_registry_row"] for v in m["variants"]) == [59, 60, 63, 64, 67, 68]



def test_full_raw_registry_snapshot_and_collision_rows_are_retained_as_evidence():
    m = load_manifest()
    snap = m["source"]["raw_registry_snapshot"]
    assert snap["rows"] == 98
    assert snap["in_repository"] is False
    assert len(snap["sha256"]) == 64
    assert len(m["source_rows"]) == 6
    assert [int(r["row_no"]) for r in m["source_rows"]] == [59, 60, 63, 64, 67, 68]
    for r in m["source_rows"]:
        assert r["carrier_id"] in {c["legacy_carrier_id"] for c in m["collisions"]}
        assert int(r["declared_bytes"]) == int(r["actual_bytes"])
        assert len(r["actual_sha256"]) == 64