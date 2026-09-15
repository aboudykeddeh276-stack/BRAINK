import copy
import hashlib

import pytest

from enterprise.metacircular_vfs_executor_r40 import (
    EMBEDDED_CORE_SOURCE,
    MetacircularVFSExecutor,
    SourcePolicy,
)


class FakeNodeVFS:
    def __init__(self):
        self.cells = {}

    def write(self, node_id, path, value):
        logical = f"vfs://node/{node_id}/{path}"
        self.cells[logical] = copy.deepcopy(value)
        return {
            "logical": logical,
            "backing": "fake://" + logical,
            "result": {"status": "COMMITTED"},
        }

    def read(self, node_id, path):
        logical = f"vfs://node/{node_id}/{path}"
        if logical not in self.cells:
            return {"logical": logical, "result": {"status": "HOLE"}}
        return {
            "logical": logical,
            "result": {"status": "READ", "value": copy.deepcopy(self.cells[logical])},
        }


CAPABILITY = {
    "status": "RESOLVED",
    "name": "runtime.generated-module.execute",
    "implementation_ref": "enterprise/metacircular_vfs_executor_r40.py",
}


def source_hash(source=EMBEDDED_CORE_SOURCE):
    return hashlib.sha256(source.encode()).hexdigest()


def test_source_policy_accepts_bounded_embedded_source():
    assert SourcePolicy.validate(EMBEDDED_CORE_SOURCE)["status"] == "VALIDATED"


@pytest.mark.parametrize(
    "source",
    [
        "import os\n",
        "def run_nested_verification(key, seed, deep_generation):\n    return eval('1')\n",
        "def run_nested_verification(key, seed, deep_generation):\n    return open('/tmp/x')\n",
    ],
)
def test_source_policy_rejects_unsafe_source(source):
    assert SourcePolicy.validate(source)["status"].startswith("FAILED:")


def test_executes_from_vfs_and_persists_receipt():
    vfs = FakeNodeVFS()
    executor = MetacircularVFSExecutor(node_vfs=vfs)
    out = executor.execute(
        node_id="node-a",
        root_seed="seed",
        secret_key=b"key",
        generation=1,
        source=EMBEDDED_CORE_SOURCE,
        expected_source_sha256=source_hash(),
        capability_resolution=CAPABILITY,
    )
    assert out["status"] == "VALIDATED_BOUNDED"
    receipt = out["receipt"]
    assert receipt["source_uri"] == "vfs://node/node-a/sys/metacircular/generation_1_core"
    assert receipt["logical_capacity_bytes"] == 100 * 1024**4
    stored = vfs.cells["vfs://node/node-a/sys/metacircular/generation_1_receipt"]
    assert stored["receipt_root"] == receipt["receipt_root"]


def test_distinct_generations_have_distinct_proofs():
    vfs = FakeNodeVFS()
    executor = MetacircularVFSExecutor(node_vfs=vfs)
    one = executor.execute(
        node_id="n", root_seed="seed", secret_key=b"k", generation=1,
        source=EMBEDDED_CORE_SOURCE, expected_source_sha256=source_hash(),
        capability_resolution=CAPABILITY,
    )
    two = executor.execute(
        node_id="n", root_seed="seed", secret_key=b"k", generation=2,
        source=EMBEDDED_CORE_SOURCE, expected_source_sha256=source_hash(),
        capability_resolution=CAPABILITY,
    )
    assert one["receipt"]["nested_proof_root"] != two["receipt"]["nested_proof_root"]


def test_hash_mismatch_blocks_before_vfs_write():
    vfs = FakeNodeVFS()
    executor = MetacircularVFSExecutor(node_vfs=vfs)
    with pytest.raises(ValueError, match="SOURCE_HASH_MISMATCH"):
        executor.execute(
            node_id="n", root_seed="seed", secret_key=b"k", generation=1,
            source=EMBEDDED_CORE_SOURCE, expected_source_sha256="0" * 64,
            capability_resolution=CAPABILITY,
        )
    assert vfs.cells == {}


def test_capability_must_already_be_resolved():
    vfs = FakeNodeVFS()
    executor = MetacircularVFSExecutor(node_vfs=vfs)
    with pytest.raises(PermissionError, match="BLOCKED:CAPABILITY"):
        executor.execute(
            node_id="n", root_seed="seed", secret_key=b"k", generation=1,
            source=EMBEDDED_CORE_SOURCE, expected_source_sha256=source_hash(),
            capability_resolution={"status": "UNKNOWN_CAPABILITY"},
        )
    assert vfs.cells == {}


def test_source_tamper_after_write_is_detected():
    class TamperVFS(FakeNodeVFS):
        def read(self, node_id, path):
            out = super().read(node_id, path)
            if out["result"]["status"] == "READ" and path.endswith("_core"):
                out["result"]["value"]["source"] += "\n#tamper"
            return out

    executor = MetacircularVFSExecutor(node_vfs=TamperVFS())
    with pytest.raises(RuntimeError, match="FAILED:VFS_SOURCE_BYTES_READBACK"):
        executor.execute(
            node_id="n", root_seed="seed", secret_key=b"k", generation=1,
            source=EMBEDDED_CORE_SOURCE, expected_source_sha256=source_hash(),
            capability_resolution=CAPABILITY,
        )
