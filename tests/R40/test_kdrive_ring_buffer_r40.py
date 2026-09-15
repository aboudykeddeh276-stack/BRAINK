from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import struct

import pytest

from enterprise.kdrive_ring_buffer_r40 import (
    FRAME_SIZE,
    FixedWirePacket,
    KDriveFixedRing,
    LatencyPolicy,
    LoopbackProfiler,
    VirtualSectorMapper,
    sha256,
)

KEY = b"test-kdrive-key"
SEED = "KEX-REHYDRATE::TEST"


def make_packet():
    address = VirtualSectorMapper.address_hash("vfs://node/test/a")
    return FixedWirePacket.create(
        key=KEY,
        epoch=1,
        sequence=1,
        window_id=0,
        coords=VirtualSectorMapper.coordinates(address),
        address_hash=address,
        payload_hash=sha256(b"payload"),
        parent_root=sha256(b"parent"),
    )


def test_wire_size_is_derived_and_round_trip_is_exact():
    assert struct.calcsize("!QQQqqq32s32s32s") == 144
    assert FRAME_SIZE == struct.calcsize("!QQQqqq32s32s32s32s") == 176
    packet = make_packet()
    raw = packet.pack()
    assert len(raw) == FRAME_SIZE
    decoded = FixedWirePacket.unpack(raw)
    assert decoded == packet
    assert decoded.verify(KEY)


def test_corrupted_wire_packet_fails_authentication():
    raw = bytearray(make_packet().pack())
    raw[40] ^= 0x01
    corrupted = FixedWirePacket.unpack(bytes(raw))
    assert not corrupted.verify(KEY)


def test_mapping_is_deterministic_and_nonzero():
    digest = VirtualSectorMapper.address_hash("vfs://node/a/state")
    assert digest == VirtualSectorMapper.address_hash("vfs://node/a/state")
    coords = VirtualSectorMapper.coordinates(digest)
    assert all(value != 0 for value in coords)
    assert coords == VirtualSectorMapper.coordinates(digest)


def test_ring_wraps_without_logical_address_index():
    ring = KDriveFixedRing(root_seed_manifest=SEED, secret_key=KEY, capacity=3)
    assert not hasattr(ring, "address_lattice")
    assert not hasattr(ring, "object_store")
    for i in range(4):
        ring.append(f"vfs://node/test/item-{i}", f"value-{i}")
    assert ring.retained_sequences() == [2, 3, 4]
    assert ring.read("vfs://node/test/item-0") is None
    assert ring.read("vfs://node/test/item-3") == b"value-3"
    assert ring.verify()["status"] == "VERIFIED"


def test_window_checkpoint_reanchors_next_window():
    ring = KDriveFixedRing(root_seed_manifest=SEED, secret_key=KEY, capacity=2)
    receipts = [ring.append(f"vfs://node/test/{i}", str(i)) for i in range(5)]
    assert receipts[1]["checkpoint_root"] is not None
    assert receipts[3]["checkpoint_root"] is not None
    checkpoints = list(ring.checkpoints)
    assert len(checkpoints) == 2
    assert checkpoints[1].previous_checkpoint_root == checkpoints[0].signature
    retained = sorted((slot for slot in ring.slots if slot), key=lambda x: x.packet.sequence)
    packet5 = next(slot.packet for slot in retained if slot.packet.sequence == 5)
    assert packet5.parent_root == checkpoints[1].signature
    assert ring.verify()["status"] == "VERIFIED"


def test_persistence_restore_and_integrity(tmp_path: Path):
    ring = KDriveFixedRing(root_seed_manifest=SEED, secret_key=KEY, capacity=3, mount_dir=tmp_path)
    for i in range(5):
        ring.append(f"vfs://node/test/{i}", f"payload-{i}")
    restored = KDriveFixedRing.restore(root_seed_manifest=SEED, secret_key=KEY, mount_dir=tmp_path)
    assert restored.retained_sequences() == [3, 4, 5]
    assert restored.read("vfs://node/test/4") == b"payload-4"
    assert restored.verify()["status"] == "VERIFIED"


def test_persistence_failure_rolls_back_memory(tmp_path: Path, monkeypatch):
    ring = KDriveFixedRing(root_seed_manifest=SEED, secret_key=KEY, capacity=3, mount_dir=tmp_path)
    initial_root = ring.chain_root

    def fail():
        raise OSError("synthetic fsync failure")

    monkeypatch.setattr(ring, "_persist_manifest", fail)
    with pytest.raises(OSError):
        ring.append("vfs://node/test/fail", b"x")
    assert ring.next_sequence == 1
    assert ring.retained_sequences() == []
    assert ring.chain_root == initial_root


def test_manifest_tamper_is_detected(tmp_path: Path):
    ring = KDriveFixedRing(root_seed_manifest=SEED, secret_key=KEY, capacity=3, mount_dir=tmp_path)
    ring.append("vfs://node/test/a", b"payload")
    manifest = tmp_path / "kdrive_ring_manifest.json"
    data = json.loads(manifest.read_text())
    packet_hex = bytearray.fromhex(data["slots"][0]["packet"])
    packet_hex[50] ^= 1
    data["slots"][0]["packet"] = packet_hex.hex()
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="MANIFEST_VERIFICATION_FAILED"):
        KDriveFixedRing.restore(root_seed_manifest=SEED, secret_key=KEY, mount_dir=tmp_path)


def test_concurrent_appends_reserve_unique_sequences():
    ring = KDriveFixedRing(root_seed_manifest=SEED, secret_key=KEY, capacity=32)

    def write(i):
        return ring.append(f"vfs://node/test/concurrent-{i}", str(i))["sequence"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        sequences = list(pool.map(write, range(20)))
    assert sorted(sequences) == list(range(1, 21))
    assert ring.verify()["status"] == "VERIFIED"


def test_local_loopback_uses_monotonic_rtt_and_verifies_frame():
    packet = make_packet()
    sample = LoopbackProfiler(KEY).measure(packet)
    assert sample["status"] == "MEASURED"
    assert sample["scope"] == "LOCAL_TCP_LOOPBACK_RTT"
    assert sample["clock"] == "monotonic_ns"
    assert sample["rtt_ns"] > 0


def test_0297_is_telemetry_policy_only():
    policy = LatencyPolicy(target_ns=297_000_000, tolerance_ns=50_000_000)
    assert policy.classify(297_000_000) == "WITHIN_TOLERANCE"
    assert policy.classify(0) == "OUTSIDE_TOLERANCE"
    ring = KDriveFixedRing(root_seed_manifest=SEED, secret_key=KEY, capacity=3)
    receipt = ring.append("vfs://node/test/no-timing-gate", b"payload")
    assert receipt["status"] == "COMMITTED"
