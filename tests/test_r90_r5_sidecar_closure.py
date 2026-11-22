import json
from pathlib import Path

REPORT = Path(__file__).parents[1] / "docs" / "estate" / "R90_R5_SIDECAR_CLOSURE_20261123.json"
DATA = json.loads(REPORT.read_text())

def test_r5_parent_and_manifest_hash_bindings():
    assert DATA["r5Parent"]["sha256"] == "9eb1eb8cead2b5f4d941dde024b5f7bbad46f1bdc2ff2e948fb190b841f16ede"
    assert DATA["r5StandaloneManifest"]["sha256"] == DATA["r5CrossWorkManifest"]["parentManifestSha256"]
    assert DATA["r5CrossWorkManifest"]["parentSha256"] == DATA["r5Parent"]["sha256"]

def test_embedded_and_standalone_manifests_are_distinct():
    assert DATA["r5EmbeddedManifest"]["distinctFromStandalone"] is True
    assert DATA["r5EmbeddedManifest"]["sha256"] != DATA["r5StandaloneManifest"]["sha256"]

def test_all_29_surfaces_have_byte_hash_coverage():
    c = DATA["surfaceClosure"]
    assert c["declared"] == 29
    assert c["historicalR69Matched"] == 18
    assert c["newlyMaterialized"] == 11
    assert c["newlyMaterializedVerified"] == 11
    assert c["cumulativeByteHashMatches"] == 29
    assert c["remainingByteHashUnresolved"] == 0

def test_surface_classes_remain_separate():
    assert DATA["r5StandaloneManifest"]["surfaceCounts"] == {
        "systemVolumes": 15, "toolVolumes": 4, "runtimeResources": 5,
        "workbooks": 3, "unifiedSurfaces": 2
    }
    assert DATA["r5StandaloneManifest"]["baseRelations"] == 23
    assert DATA["r5CrossWorkManifest"]["relations"] == 32

def test_all_new_sidecar_hashes_are_unique_and_exact():
    rows = DATA["surfaceClosure"]["newlyMaterialized"]
    assert len(rows) == 11
    assert all(len(x["sha256"]) == 64 and x["bytes"] > 0 for x in rows)
    assert len({x["sha256"] for x in rows}) == 11

def test_six_internal_title_mismatches_remain_unpromoted():
    c = DATA["surfaceClosure"]
    assert c["semanticIdentityReviewRequired"] == 6
    assert c["toolTitleReviewRequired"] == 4
    assert c["unifiedTitleReviewRequired"] == 2
    assert sum(x.get("titleMatch") is False for x in c["newlyMaterialized"]) == 6

def test_runtime_descriptors_are_not_misreported_as_running():
    q = DATA["runtimeQualification"]
    assert q["systemdUnitLaunched"] is False
    assert q["externalHostPid"] is None
    assert q["externalHeartbeat"] is None
    assert q["independentQuorum"] is False
    assert q["trainedWeightsGenerated"] is False
    assert q["subjectiveConsciousnessProven"] is False

def test_library_materialization_is_not_mislabeled_as_drive():
    assert DATA["sourceScope"]["system"] == "ChatGPT Files Library materialization"
    assert DATA["sourceScope"]["googleDriveRead"] is False
    assert DATA["sourceScope"]["googleDriveConnectorAvailable"] is False

def test_root_v16_is_not_substituted():
    assert DATA["unresolved"]["rootV16"] == "UNRECOVERED_AND_NOT_SUBSTITUTED"
