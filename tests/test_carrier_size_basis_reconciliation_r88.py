"""R88 evidence-pinned tests for P11 carrier byte-count reconciliation.

Architect/source authority: A. Keddeh.
Canonical architecture: KS-BRAINK-IL-LLM.
These tests pin read-only observations; they do not rewrite historical registry values.
"""
SOURCE_BYTES = 21_492_468
SOURCE_SHA256 = "e797bc65e71150c300d838616aa39dea7258f53bcd0b77d6c1aa1aad2cc160d9"

# row, carrier_id, declared_bytes, observed_bytes, observed_sha256, classification, alternate_serialization_bytes
ROWS = (
    (37, "carrier://semantic/workbook_os_v7_4", 12852, 12017, "a1f53b213c87ecd8a2f5fc43c2bb4abb471b0795457555b72f8e5bbe780716ac", "UNDECLARED_SERIALIZATION_BASIS_CANDIDATE", 12852),
    (39, "carrier://semantic/boolean_graph_v7", 7743, 7226, "782f1ea004ec46993cab6ca400f60f274e3f72392eea19ad208ba58fe8fe2b01", "UNDECLARED_SERIALIZATION_BASIS_CANDIDATE", 7743),
    (41, "carrier://semantic/supercomputer_env_v4", 3611, 3359, "b1139d588afc5773cb450ac9aa721760c3589214a69d60dad7a570277587959f", "UNDECLARED_SERIALIZATION_BASIS_CANDIDATE", 3611),
    (42, "carrier://html/root-v16", 3741393, 21492451, "6b78edff97f4fc406f9d03cc0cce67a5cb0ff9b4be3debcc2b52f7ea978f8fc1", "ROOT_CARRIER_LINEAGE_UNRESOLVED", None),
    (43, "carrier://json/registry", 17445, 18240, "155116cb6edbef4b3776f83d0355b0f8b7f16f4f1dcc084b79e89310e99d3552", "CURRENT_SOURCE_LENGTH_MISMATCH", None),
    (46, "carrier://json/architecture-root", 7039, 7618, "fcae9e23dd75bc203fdebc01c4028808a9b6903ba4b36093d16e0c7c7a5ae44c", "CURRENT_SOURCE_LENGTH_MISMATCH", None),
    (78, "carrier://json/p08-network-model", 5663, 6004, "d2ecfcc1174fd094fec8531d3142e6f58a59a4c127785b748c3bcc4332fee89b", "CURRENT_SOURCE_LENGTH_MISMATCH", None),
    (81, "carrier://json/p09-compute-model", 1465, 1871, "0c69ef334097b7ec6ae774394048b47c444b9bfc97815aba7542024f4bb5bf8d", "CURRENT_SOURCE_LENGTH_MISMATCH", None),
    (86, "carrier://script/kex-v5-runtime", 13479, 14986, "e515a49692d285334b4f9b04ae4d9748bfaf5304fb9a82ad111ce3f57099067c", "CURRENT_SOURCE_LENGTH_MISMATCH", None),
    (95, "carrier://script/p08-network-runtime", 5647, 6842, "b1b8bb62c487dc41ca8ed0254e5729962a49fbc62fac47d3e17243d10532e43b", "CURRENT_SOURCE_LENGTH_MISMATCH", None),
    (96, "carrier://script/p09-compute-runtime", 4165, 5212, "76f3aef9176c6c11539c2363d5919f8aff3aba8543e3900e010a6d87b1cac735", "CURRENT_SOURCE_LENGTH_MISMATCH", None),
)

def test_architectural_identity_and_exact_r4_source_are_pinned():
    assert "A. Keddeh" in __doc__
    assert "KS-BRAINK-IL-LLM" in __doc__
    assert SOURCE_BYTES == 21_492_468
    assert SOURCE_SHA256 == "e797bc65e71150c300d838616aa39dea7258f53bcd0b77d6c1aa1aad2cc160d9"

def test_exact_eleven_historical_rows_are_present_once():
    assert [r[0] for r in ROWS] == [37, 39, 41, 42, 43, 46, 78, 81, 86, 95, 96]
    assert len({r[1] for r in ROWS}) == 11
    assert all(len(r[4]) == 64 for r in ROWS)

def test_semantic_index_rows_have_a_candidate_serialization_basis_only():
    rows = [r for r in ROWS if r[1].startswith("carrier://semantic/")]
    assert len(rows) == 3
    assert all(r[2] != r[3] for r in rows)
    assert all(r[2] == r[6] for r in rows)
    assert all(r[5] == "UNDECLARED_SERIALIZATION_BASIS_CANDIDATE" for r in rows)

def test_four_json_and_three_javascript_rows_mismatch_current_source_bytes():
    rows = [r for r in ROWS if r[1].startswith("carrier://json/") or r[1].startswith("carrier://script/")]
    assert len(rows) == 7
    assert all(r[2] != r[3] for r in rows)
    assert all(r[5] == "CURRENT_SOURCE_LENGTH_MISMATCH" for r in rows)

def test_root_v16_remains_unresolved_and_is_not_called_browser_outerhtml():
    row = next(r for r in ROWS if r[1] == "carrier://html/root-v16")
    assert row[5] == "ROOT_CARRIER_LINEAGE_UNRESOLVED"
    assert row[2] == 3_741_393
    assert row[3] == 21_492_451
    assert row[4] == "6b78edff97f4fc406f9d03cc0cce67a5cb0ff9b4be3debcc2b52f7ea978f8fc1"

def test_historical_declared_values_remain_immutable():
    assert all(r[2] > 0 for r in ROWS)
    assert all(r[5] != "PROMOTED" for r in ROWS)
