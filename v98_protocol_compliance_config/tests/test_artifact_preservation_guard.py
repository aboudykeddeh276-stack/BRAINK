from pathlib import Path

from keddeh_artifact_preservation_guard import ArtifactPreservationGuard

ROOT = Path(__file__).resolve().parents[1]


def test_registry_is_complete():
    assert ArtifactPreservationGuard(ROOT).validate_registry() == []


def test_scratch_path_requires_reconciliation():
    result = ArtifactPreservationGuard(ROOT).scan_text(
        "Export complete: sandbox:/workspace/scratch/abc/build.zip"
    )
    assert result["requires_durability_reconciliation"] is True
    assert result["ephemeral_references"] == [
        "sandbox:/workspace/scratch/abc/build.zip"
    ]


def test_missing_file_is_not_saved(tmp_path):
    result = ArtifactPreservationGuard(ROOT).verify_file(tmp_path / "missing.zip")
    assert result["state"] == "MISSING_BYTES_CONFIRMED"
    assert result["durable_bytes_verified"] is False


def test_existing_file_requires_byte_readback(tmp_path):
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("persisted", encoding="utf-8")
    result = ArtifactPreservationGuard(ROOT).verify_file(artifact)
    assert result["state"] == "DURABLE_BYTES_VERIFIED"
    assert result["byte_size"] == 9
    assert len(result["sha256"]) == 64


def test_hash_mismatch_rejects_completion(tmp_path):
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("persisted", encoding="utf-8")
    result = ArtifactPreservationGuard(ROOT).verify_file(artifact, "0" * 64)
    assert result["state"] == "HASH_MISMATCH"
    assert result["durable_bytes_verified"] is False
