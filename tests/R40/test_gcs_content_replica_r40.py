from pathlib import Path
import pytest

from enterprise.gcs_content_replica_r40 import ContentAddressedGCSReplica


def make(tmp_path):
    return ContentAddressedGCSReplica(mount_root=tmp_path/"mount", bucket="test-bucket", require_mount=False)


def test_put_and_verify(tmp_path):
    target = make(tmp_path)
    receipt = target.put_bytes(kind="ledger", payload=b"abc")
    assert receipt.gs_uri.startswith("gs://test-bucket/")
    assert target.verify(receipt)["status"] == "VERIFIED"


def test_same_payload_is_idempotent(tmp_path):
    target = make(tmp_path)
    a = target.put_bytes(kind="artifact", payload=b"same")
    b = target.put_bytes(kind="artifact", payload=b"same")
    assert a.sha256 == b.sha256
    assert a.relative_object == b.relative_object


def test_existing_corruption_fails_closed(tmp_path):
    target = make(tmp_path)
    receipt = target.put_bytes(kind="ledger", payload=b"abc")
    Path(receipt.local_mount_path).write_bytes(b"corrupt")
    with pytest.raises(RuntimeError, match="EXISTING_OBJECT_HASH_MISMATCH"):
        target.put_bytes(kind="ledger", payload=b"abc")


def test_verify_detects_corruption(tmp_path):
    target = make(tmp_path)
    receipt = target.put_bytes(kind="proof", payload=b"abc")
    Path(receipt.local_mount_path).write_bytes(b"x")
    assert target.verify(receipt)["status"] == "FAILED:REPLICA_HASH_MISMATCH"


@pytest.mark.parametrize("bad", ["../x", "x/y", "", ".", ".."])
def test_segment_rejection(tmp_path, bad):
    target = make(tmp_path)
    with pytest.raises(ValueError):
        target.put_bytes(kind=bad, payload=b"x")


def test_replica_role_is_not_canonical(tmp_path):
    target = make(tmp_path)
    probe = target.probe()
    assert probe["authority"] == "REPLICA_ONLY"
    assert "NO_FIXED_VOLUME" in probe["capacity_model"]
