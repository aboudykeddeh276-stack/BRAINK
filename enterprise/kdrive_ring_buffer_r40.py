from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import socket
import struct
import tempfile
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = "braink.kdrive.fixed-ring.r40/v1"
CHECKPOINT_SCHEMA = "braink.kdrive.window-checkpoint.r40/v1"
MANIFEST_SCHEMA = "braink.kdrive.ring-manifest.r40/v1"

_UNSIGNED_STRUCT = struct.Struct("!QQQqqq32s32s32s")
_PACKET_STRUCT = struct.Struct("!QQQqqq32s32s32s32s")
FRAME_SIZE = _PACKET_STRUCT.size
HASH_BYTES = 32
MAX_U64 = (1 << 64) - 1
MAX_I64 = (1 << 63) - 1
MIN_I64 = -(1 << 63)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def hmac_sha256(key: bytes, message: bytes) -> bytes:
    if not isinstance(key, (bytes, bytearray)) or not key:
        raise ValueError("SECRET_KEY_REQUIRED")
    return hmac.new(bytes(key), message, digestmod=hashlib.sha256).digest()


def _check_hash(value: bytes, field: str) -> bytes:
    raw = bytes(value)
    if len(raw) != HASH_BYTES:
        raise ValueError(f"{field}_MUST_BE_32_BYTES")
    return raw


def _check_u64(value: int, field: str) -> int:
    value = int(value)
    if value < 0 or value > MAX_U64:
        raise ValueError(f"{field}_OUT_OF_RANGE")
    return value


def _check_i64(value: int, field: str) -> int:
    value = int(value)
    if value < MIN_I64 or value > MAX_I64:
        raise ValueError(f"{field}_OUT_OF_RANGE")
    return value


@dataclass(frozen=True)
class FixedWirePacket:
    epoch: int
    sequence: int
    window_id: int
    coord_x: int
    coord_y: int
    coord_z: int
    address_hash: bytes
    payload_hash: bytes
    parent_root: bytes
    signature: bytes

    def unsigned_bytes(self) -> bytes:
        return _UNSIGNED_STRUCT.pack(
            _check_u64(self.epoch, "epoch"),
            _check_u64(self.sequence, "sequence"),
            _check_u64(self.window_id, "window_id"),
            _check_i64(self.coord_x, "coord_x"),
            _check_i64(self.coord_y, "coord_y"),
            _check_i64(self.coord_z, "coord_z"),
            _check_hash(self.address_hash, "address_hash"),
            _check_hash(self.payload_hash, "payload_hash"),
            _check_hash(self.parent_root, "parent_root"),
        )

    def pack(self) -> bytes:
        return self.unsigned_bytes() + _check_hash(self.signature, "signature")

    def verify(self, key: bytes) -> bool:
        expected = hmac_sha256(key, self.unsigned_bytes())
        return hmac.compare_digest(expected, _check_hash(self.signature, "signature"))

    @classmethod
    def create(
        cls,
        *,
        key: bytes,
        epoch: int,
        sequence: int,
        window_id: int,
        coords: tuple[int, int, int],
        address_hash: bytes,
        payload_hash: bytes,
        parent_root: bytes,
    ) -> "FixedWirePacket":
        unsigned = _UNSIGNED_STRUCT.pack(
            _check_u64(epoch, "epoch"),
            _check_u64(sequence, "sequence"),
            _check_u64(window_id, "window_id"),
            _check_i64(coords[0], "coord_x"),
            _check_i64(coords[1], "coord_y"),
            _check_i64(coords[2], "coord_z"),
            _check_hash(address_hash, "address_hash"),
            _check_hash(payload_hash, "payload_hash"),
            _check_hash(parent_root, "parent_root"),
        )
        return cls(
            epoch=int(epoch),
            sequence=int(sequence),
            window_id=int(window_id),
            coord_x=int(coords[0]),
            coord_y=int(coords[1]),
            coord_z=int(coords[2]),
            address_hash=bytes(address_hash),
            payload_hash=bytes(payload_hash),
            parent_root=bytes(parent_root),
            signature=hmac_sha256(key, unsigned),
        )

    @classmethod
    def unpack(cls, data: bytes) -> "FixedWirePacket":
        if len(data) != FRAME_SIZE:
            raise ValueError(f"FRAME_SIZE_MISMATCH:{len(data)}!={FRAME_SIZE}")
        values = _PACKET_STRUCT.unpack(data)
        return cls(
            epoch=values[0], sequence=values[1], window_id=values[2],
            coord_x=values[3], coord_y=values[4], coord_z=values[5],
            address_hash=values[6], payload_hash=values[7],
            parent_root=values[8], signature=values[9],
        )


class VirtualSectorMapper:
    """Deterministic address-to-coordinate projection with no mutable index table."""

    @staticmethod
    def normalize_uri(vfs_uri: str) -> str:
        value = str(vfs_uri)
        if not value.startswith("vfs://"):
            raise ValueError("VFS_URI_REQUIRED")
        if "\x00" in value:
            raise ValueError("VFS_URI_CONTAINS_NUL")
        if len(value.encode("utf-8")) > 4096:
            raise ValueError("VFS_URI_TOO_LONG")
        return value

    @classmethod
    def address_hash(cls, vfs_uri: str) -> bytes:
        return sha256(cls.normalize_uri(vfs_uri).encode("utf-8"))

    @staticmethod
    def coordinates(address_hash: bytes) -> tuple[int, int, int]:
        digest = _check_hash(address_hash, "address_hash")
        values = []
        for offset in (0, 8, 16):
            value = int.from_bytes(digest[offset:offset + 8], "big") & MAX_I64
            values.append(value or 1)
        return values[0], values[1], values[2]


@dataclass(frozen=True)
class StoredSlot:
    packet: FixedWirePacket
    payload: bytes


@dataclass(frozen=True)
class WindowCheckpoint:
    window_id: int
    first_sequence: int
    last_sequence: int
    previous_checkpoint_root: bytes
    terminal_packet_root: bytes
    signature: bytes

    def body(self) -> dict[str, Any]:
        return {
            "schema": CHECKPOINT_SCHEMA,
            "window_id": self.window_id,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "previous_checkpoint_root": self.previous_checkpoint_root.hex(),
            "terminal_packet_root": self.terminal_packet_root.hex(),
        }

    @classmethod
    def create(cls, *, key: bytes, window_id: int, first_sequence: int, last_sequence: int,
               previous_checkpoint_root: bytes, terminal_packet_root: bytes) -> "WindowCheckpoint":
        body = {
            "schema": CHECKPOINT_SCHEMA,
            "window_id": _check_u64(window_id, "window_id"),
            "first_sequence": _check_u64(first_sequence, "first_sequence"),
            "last_sequence": _check_u64(last_sequence, "last_sequence"),
            "previous_checkpoint_root": _check_hash(previous_checkpoint_root, "previous_checkpoint_root").hex(),
            "terminal_packet_root": _check_hash(terminal_packet_root, "terminal_packet_root").hex(),
        }
        return cls(
            window_id=body["window_id"], first_sequence=body["first_sequence"], last_sequence=body["last_sequence"],
            previous_checkpoint_root=bytes.fromhex(body["previous_checkpoint_root"]),
            terminal_packet_root=bytes.fromhex(body["terminal_packet_root"]),
            signature=hmac_sha256(key, canonical_json(body)),
        )

    def verify(self, key: bytes) -> bool:
        return hmac.compare_digest(hmac_sha256(key, canonical_json(self.body())), self.signature)

    def to_dict(self) -> dict[str, Any]:
        return {**self.body(), "signature": self.signature.hex()}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "WindowCheckpoint":
        if value.get("schema") != CHECKPOINT_SCHEMA:
            raise ValueError("CHECKPOINT_SCHEMA_MISMATCH")
        return cls(
            window_id=int(value["window_id"]), first_sequence=int(value["first_sequence"]),
            last_sequence=int(value["last_sequence"]),
            previous_checkpoint_root=bytes.fromhex(value["previous_checkpoint_root"]),
            terminal_packet_root=bytes.fromhex(value["terminal_packet_root"]),
            signature=bytes.fromhex(value["signature"]),
        )


class KDriveFixedRing:
    """Bounded authenticated packet ring.

    Local storage primitive only. It does not implement distributed consensus,
    WebRTC, secure memory erasure, or a global address index.
    """

    def __init__(self, *, root_seed_manifest: str, secret_key: bytes, capacity: int = 1024,
                 epoch: int = 1, mount_dir: str | os.PathLike[str] | None = None,
                 max_payload_bytes: int = 4 * 1024 * 1024, checkpoint_history: int = 16):
        if int(capacity) < 2:
            raise ValueError("CAPACITY_MUST_BE_AT_LEAST_2")
        if int(max_payload_bytes) < 1:
            raise ValueError("MAX_PAYLOAD_BYTES_INVALID")
        if int(checkpoint_history) < 2:
            raise ValueError("CHECKPOINT_HISTORY_MUST_BE_AT_LEAST_2")
        self.root_seed_manifest = str(root_seed_manifest)
        self.secret_key = bytes(secret_key)
        if not self.secret_key:
            raise ValueError("SECRET_KEY_REQUIRED")
        self.capacity = int(capacity)
        self.epoch = _check_u64(epoch, "epoch")
        self.max_payload_bytes = int(max_payload_bytes)
        self.checkpoint_history = int(checkpoint_history)
        self.slots: list[StoredSlot | None] = [None] * self.capacity
        self.next_sequence = 1
        self.genesis_root = hmac_sha256(self.secret_key, b"KDRIVE_RING_GENESIS\x00" + self.root_seed_manifest.encode())
        self.chain_root = self.genesis_root
        self.last_checkpoint_root = self.genesis_root
        self.checkpoints: deque[WindowCheckpoint] = deque(maxlen=self.checkpoint_history)
        self._lock = threading.RLock()
        self.mount_dir = Path(mount_dir).expanduser() if mount_dir is not None else None
        self.manifest_path = self.mount_dir / "kdrive_ring_manifest.json" if self.mount_dir else None
        if self.mount_dir is not None:
            self.mount_dir.mkdir(parents=True, exist_ok=True)

    def _packet_for(self, *, sequence: int, address_hash: bytes, payload_hash: bytes) -> FixedWirePacket:
        return FixedWirePacket.create(
            key=self.secret_key, epoch=self.epoch, sequence=sequence,
            window_id=(sequence - 1) // self.capacity,
            coords=VirtualSectorMapper.coordinates(address_hash), address_hash=address_hash,
            payload_hash=payload_hash, parent_root=self.chain_root,
        )

    def append(self, vfs_uri: str, payload: bytes | bytearray | memoryview | str) -> dict[str, Any]:
        uri = VirtualSectorMapper.normalize_uri(vfs_uri)
        payload_bytes = payload.encode() if isinstance(payload, str) else bytes(payload)
        if len(payload_bytes) > self.max_payload_bytes:
            raise ValueError("PAYLOAD_TOO_LARGE")
        address_hash = VirtualSectorMapper.address_hash(uri)
        payload_hash = sha256(payload_bytes)

        with self._lock:
            sequence = self.next_sequence
            slot_index = (sequence - 1) % self.capacity
            rollback = (self.slots[slot_index], self.next_sequence, self.chain_root,
                        self.last_checkpoint_root, list(self.checkpoints))
            packet = self._packet_for(sequence=sequence, address_hash=address_hash, payload_hash=payload_hash)
            self.slots[slot_index] = StoredSlot(packet=packet, payload=payload_bytes)
            self.next_sequence = sequence + 1
            self.chain_root = packet.signature

            checkpoint = None
            if sequence % self.capacity == 0:
                checkpoint = WindowCheckpoint.create(
                    key=self.secret_key, window_id=packet.window_id,
                    first_sequence=sequence - self.capacity + 1, last_sequence=sequence,
                    previous_checkpoint_root=self.last_checkpoint_root,
                    terminal_packet_root=packet.signature,
                )
                self.checkpoints.append(checkpoint)
                self.last_checkpoint_root = checkpoint.signature
                self.chain_root = checkpoint.signature
            try:
                if self.manifest_path is not None:
                    self._persist_manifest()
            except Exception:
                old_slot, old_next, old_chain, old_checkpoint_root, old_checkpoints = rollback
                self.slots[slot_index] = old_slot
                self.next_sequence = old_next
                self.chain_root = old_chain
                self.last_checkpoint_root = old_checkpoint_root
                self.checkpoints = deque(old_checkpoints, maxlen=self.checkpoint_history)
                raise

            return {
                "status": "COMMITTED", "schema": SCHEMA, "sequence": sequence,
                "window_id": packet.window_id, "slot": slot_index,
                "address_hash": address_hash.hex(), "payload_hash": payload_hash.hex(),
                "packet_root": packet.signature.hex(), "chain_root": self.chain_root.hex(),
                "checkpoint_root": None if checkpoint is None else checkpoint.signature.hex(),
            }

    def read(self, vfs_uri: str) -> bytes | None:
        address_hash = VirtualSectorMapper.address_hash(vfs_uri)
        with self._lock:
            matches = [slot for slot in self.slots if slot is not None and slot.packet.address_hash == address_hash]
            if not matches:
                return None
            latest = max(matches, key=lambda item: item.packet.sequence)
            if sha256(latest.payload) != latest.packet.payload_hash:
                raise RuntimeError("PAYLOAD_HASH_MISMATCH")
            if not latest.packet.verify(self.secret_key):
                raise RuntimeError("PACKET_SIGNATURE_INVALID")
            return bytes(latest.payload)

    def retained_sequences(self) -> list[int]:
        with self._lock:
            return sorted(slot.packet.sequence for slot in self.slots if slot is not None)

    def _checkpoint_for_last_sequence(self, sequence: int) -> WindowCheckpoint | None:
        for checkpoint in reversed(self.checkpoints):
            if checkpoint.last_sequence == sequence:
                return checkpoint
        return None

    def verify(self) -> dict[str, Any]:
        with self._lock:
            entries = sorted((s for s in self.slots if s is not None), key=lambda s: s.packet.sequence)
            sequences = [s.packet.sequence for s in entries]
            if len(sequences) != len(set(sequences)):
                return {"status": "FAILED:DUPLICATE_SEQUENCE"}
            if entries and sequences[-1] >= self.next_sequence:
                return {"status": "FAILED:NEXT_SEQUENCE_INVALID"}
            for slot in entries:
                if slot.packet.window_id != (slot.packet.sequence - 1) // self.capacity:
                    return {"status": "FAILED:PACKET_WINDOW_ID_MISMATCH", "sequence": slot.packet.sequence}
                if not slot.packet.verify(self.secret_key):
                    return {"status": "FAILED:PACKET_SIGNATURE_INVALID", "sequence": slot.packet.sequence}
                if sha256(slot.payload) != slot.packet.payload_hash:
                    return {"status": "FAILED:PAYLOAD_HASH_MISMATCH", "sequence": slot.packet.sequence}
                if VirtualSectorMapper.coordinates(slot.packet.address_hash) != (
                    slot.packet.coord_x, slot.packet.coord_y, slot.packet.coord_z
                ):
                    return {"status": "FAILED:COORDINATE_MISMATCH", "sequence": slot.packet.sequence}
            retained_checkpoints = list(self.checkpoints)
            for index, checkpoint in enumerate(retained_checkpoints):
                if not checkpoint.verify(self.secret_key):
                    return {"status": "FAILED:CHECKPOINT_SIGNATURE_INVALID", "window_id": checkpoint.window_id}
                expected_first = checkpoint.window_id * self.capacity + 1
                expected_last = (checkpoint.window_id + 1) * self.capacity
                if checkpoint.first_sequence != expected_first or checkpoint.last_sequence != expected_last:
                    return {"status": "FAILED:CHECKPOINT_SEQUENCE_RANGE_INVALID", "window_id": checkpoint.window_id}
                if index > 0 and checkpoint.previous_checkpoint_root != retained_checkpoints[index - 1].signature:
                    return {"status": "FAILED:CHECKPOINT_CHAIN_MISMATCH", "window_id": checkpoint.window_id}
            if retained_checkpoints and self.last_checkpoint_root != retained_checkpoints[-1].signature:
                return {"status": "FAILED:LAST_CHECKPOINT_ROOT_MISMATCH"}
            if not retained_checkpoints and self.last_checkpoint_root != self.genesis_root:
                return {"status": "FAILED:EMPTY_CHECKPOINT_ROOT_MISMATCH"}

            verified_edges = 0
            unavailable_edges = 0
            for i, slot in enumerate(entries):
                packet = slot.packet
                if i == 0:
                    predecessor = packet.sequence - 1
                    if packet.sequence == 1:
                        expected = self.genesis_root
                    elif predecessor % self.capacity == 0:
                        checkpoint = self._checkpoint_for_last_sequence(predecessor)
                        if checkpoint is None:
                            unavailable_edges += 1
                            continue
                        expected = checkpoint.signature
                    else:
                        unavailable_edges += 1
                        continue
                else:
                    previous = entries[i - 1].packet
                    if packet.sequence != previous.sequence + 1:
                        return {"status": "FAILED:SEQUENCE_GAP_WITHIN_RETAINED_RING",
                                "previous_sequence": previous.sequence, "sequence": packet.sequence}
                    if previous.sequence % self.capacity == 0:
                        checkpoint = self._checkpoint_for_last_sequence(previous.sequence)
                        if checkpoint is None:
                            return {"status": "FAILED:CHECKPOINT_ANCHOR_MISSING", "sequence": packet.sequence}
                        expected = checkpoint.signature
                    else:
                        expected = previous.signature
                if packet.parent_root != expected:
                    return {"status": "FAILED:PARENT_ROOT_MISMATCH", "sequence": packet.sequence}
                verified_edges += 1

            if entries:
                latest = entries[-1].packet
                if latest.sequence % self.capacity == 0:
                    checkpoint = self._checkpoint_for_last_sequence(latest.sequence)
                    if checkpoint is None or self.chain_root != checkpoint.signature:
                        return {"status": "FAILED:CHAIN_ROOT_MISMATCH"}
                elif self.chain_root != latest.signature:
                    return {"status": "FAILED:CHAIN_ROOT_MISMATCH"}
            elif self.chain_root != self.genesis_root:
                return {"status": "FAILED:EMPTY_CHAIN_ROOT_MISMATCH"}

            return {
                "status": "VERIFIED", "retained_sequences": sequences,
                "parent_edges_verified": verified_edges,
                "parent_edges_unavailable": unavailable_edges,
                "verification_scope": "FULL_RETAINED_WINDOW" if unavailable_edges == 0 else "BOUNDED_RETAINED_WINDOW",
                "chain_root": self.chain_root.hex(),
            }

    def _manifest(self) -> dict[str, Any]:
        slots = []
        for index, slot in enumerate(self.slots):
            if slot is not None:
                slots.append({"slot": index, "packet": slot.packet.pack().hex(),
                              "payload_b64": base64.b64encode(slot.payload).decode("ascii")})
        return {
            "schema": MANIFEST_SCHEMA, "capacity": self.capacity, "epoch": self.epoch,
            "next_sequence": self.next_sequence,
            "root_seed_hash": sha256(self.root_seed_manifest.encode()).hex(),
            "genesis_root": self.genesis_root.hex(), "chain_root": self.chain_root.hex(),
            "last_checkpoint_root": self.last_checkpoint_root.hex(),
            "checkpoint_history": self.checkpoint_history,
            "checkpoints": [c.to_dict() for c in self.checkpoints], "slots": slots,
        }

    def _persist_manifest(self) -> None:
        if self.mount_dir is None or self.manifest_path is None:
            return
        fd, temp_path = tempfile.mkstemp(dir=self.mount_dir, prefix=".kdrive-ring-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(canonical_json(self._manifest()))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.manifest_path)
            directory_fd = os.open(self.mount_dir, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except Exception:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass
            raise

    @classmethod
    def restore(cls, *, root_seed_manifest: str, secret_key: bytes,
                mount_dir: str | os.PathLike[str], max_payload_bytes: int = 4 * 1024 * 1024) -> "KDriveFixedRing":
        manifest = Path(mount_dir).expanduser() / "kdrive_ring_manifest.json"
        value = json.loads(manifest.read_text(encoding="utf-8"))
        if value.get("schema") != MANIFEST_SCHEMA:
            raise ValueError("MANIFEST_SCHEMA_MISMATCH")
        engine = cls(
            root_seed_manifest=root_seed_manifest, secret_key=secret_key,
            capacity=int(value["capacity"]), epoch=int(value["epoch"]), mount_dir=mount_dir,
            max_payload_bytes=max_payload_bytes, checkpoint_history=int(value.get("checkpoint_history", 16)),
        )
        if value.get("root_seed_hash") != sha256(root_seed_manifest.encode()).hex():
            raise ValueError("ROOT_SEED_MISMATCH")
        if bytes.fromhex(value["genesis_root"]) != engine.genesis_root:
            raise ValueError("GENESIS_ROOT_MISMATCH")
        engine.next_sequence = int(value["next_sequence"])
        engine.chain_root = bytes.fromhex(value["chain_root"])
        engine.last_checkpoint_root = bytes.fromhex(value["last_checkpoint_root"])
        engine.checkpoints = deque((WindowCheckpoint.from_dict(v) for v in value.get("checkpoints", [])),
                                   maxlen=engine.checkpoint_history)
        engine.slots = [None] * engine.capacity
        for item in value.get("slots", []):
            index = int(item["slot"])
            if index < 0 or index >= engine.capacity:
                raise ValueError("MANIFEST_SLOT_OUT_OF_RANGE")
            engine.slots[index] = StoredSlot(
                packet=FixedWirePacket.unpack(bytes.fromhex(item["packet"])),
                payload=base64.b64decode(item["payload_b64"], validate=True),
            )
        verified = engine.verify()
        if verified.get("status") != "VERIFIED":
            raise ValueError("MANIFEST_VERIFICATION_FAILED:" + str(verified))
        return engine


@dataclass(frozen=True)
class LatencyPolicy:
    target_ns: int | None = None
    tolerance_ns: int | None = None

    def classify(self, rtt_ns: int) -> str:
        if self.target_ns is None:
            return "MEASURED"
        tolerance = 0 if self.tolerance_ns is None else int(self.tolerance_ns)
        return "WITHIN_TOLERANCE" if abs(int(rtt_ns) - int(self.target_ns)) <= tolerance else "OUTSIDE_TOLERANCE"


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("STREAM_CLOSED_BEFORE_FRAME_COMPLETE")
        data.extend(chunk)
    return bytes(data)


class LoopbackProfiler:
    """Local TCP RTT measurement in one monotonic clock domain."""

    def __init__(self, secret_key: bytes, timeout_sec: float = 2.0):
        self.secret_key = bytes(secret_key)
        self.timeout_sec = float(timeout_sec)

    def measure(self, packet: FixedWirePacket, *, policy: LatencyPolicy | None = None) -> dict[str, Any]:
        if not packet.verify(self.secret_key):
            raise ValueError("PACKET_SIGNATURE_INVALID")
        ready = threading.Event()
        state: dict[str, Any] = {}
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        server.settimeout(self.timeout_sec)
        host, port = server.getsockname()

        def serve_once() -> None:
            ready.set()
            try:
                conn, _ = server.accept()
                with conn:
                    conn.settimeout(self.timeout_sec)
                    received = FixedWirePacket.unpack(_recv_exact(conn, FRAME_SIZE))
                    if not received.verify(self.secret_key):
                        raise ValueError("PACKET_SIGNATURE_INVALID")
                    conn.sendall(received.signature)
                state["status"] = "ACKED"
            except Exception as exc:
                state["error"] = type(exc).__name__ + ":" + str(exc)
            finally:
                server.close()

        thread = threading.Thread(target=serve_once, daemon=True)
        thread.start()
        if not ready.wait(timeout=self.timeout_sec):
            raise TimeoutError("LOOPBACK_SERVER_NOT_READY")
        with socket.create_connection((host, port), timeout=self.timeout_sec) as client:
            client.settimeout(self.timeout_sec)
            started = time.monotonic_ns()
            client.sendall(packet.pack())
            ack = _recv_exact(client, HASH_BYTES)
            finished = time.monotonic_ns()
        thread.join(timeout=self.timeout_sec)
        if state.get("error"):
            raise RuntimeError(state["error"])
        if ack != packet.signature:
            raise RuntimeError("LOOPBACK_ACK_MISMATCH")
        rtt_ns = finished - started
        selected = policy or LatencyPolicy()
        return {
            "status": "MEASURED", "clock": "monotonic_ns", "scope": "LOCAL_TCP_LOOPBACK_RTT",
            "rtt_ns": rtt_ns, "rtt_sec": rtt_ns / 1_000_000_000.0,
            "policy": selected.classify(rtt_ns), "target_ns": selected.target_ns,
            "tolerance_ns": selected.tolerance_ns,
        }
