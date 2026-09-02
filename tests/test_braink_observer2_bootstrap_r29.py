import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

from braink_observer2_bootstrap_r29 import (
    BLOCK,
    BRAINK_OFF,
    SERVICE_OFF,
    MUTATION_OFF,
    BrainkMachineProbe,
    build_observer2_federation,
)
from observer2_federation_r29 import Observer2Runtime


def write_block(path: Path, off: int, obj) -> None:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    buf = bytearray(BLOCK)
    buf[:4] = len(raw).to_bytes(4, "big")
    buf[8:8 + len(raw)] = raw
    fd = os.open(path, os.O_RDWR)
    try:
        os.pwrite(fd, bytes(buf), off)
    finally:
        os.close(fd)


class BrainkObserver2BootstrapR29Tests(unittest.TestCase):
    def make_machine(self, root: Path) -> Path:
        disk = root / "braink.machine"
        with disk.open("wb") as f:
            f.truncate(MUTATION_OFF + BLOCK)
        write_block(disk, BRAINK_OFF, {
            "machine_id": "MACHINE::TEST",
            "braink_id": "BRAINK::TEST",
            "lineage_root": "LINEAGE::TEST",
        })
        write_block(disk, SERVICE_OFF, {"services": {
            "SERVER_ROOT": {"lexical_id": "LEX://SERVER/GLOBAL"},
            "DOMAIN_ROOT": {"lexical_id": "LEX://DOMAIN/keddeh.com"},
        }})
        write_block(disk, MUTATION_OFF, {"revision": 7, "objects": {"DNS": {}}})
        return disk

    def test_machine_probe_reads_existing_machine_contract_without_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            disk = self.make_machine(Path(td))
            before = disk.read_bytes()
            payload = BrainkMachineProbe(disk).sample("observer2://test")
            after = disk.read_bytes()
            self.assertEqual(before, after)
            self.assertEqual("MACHINE::TEST", payload["machine_id"])
            self.assertEqual("BRAINK::TEST", payload["braink_id"])
            self.assertEqual(7, payload["mutation_revision"])
            self.assertEqual(["DOMAIN_ROOT", "SERVER_ROOT"], payload["service_roots"])

    def test_builder_federates_repository_machine_and_process(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "observer2@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Observer2 Test"], check=True)
            (repo / "seed.txt").write_text("seed")
            subprocess.run(["git", "-C", str(repo), "add", "seed.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "seed"], check=True)
            disk = self.make_machine(root)
            federation = build_observer2_federation(repository=repo, machine_disk=disk, include_process=True)
            frame = Observer2Runtime(federation=federation).observe({"route": "federated"})
            substrates = {r.substrate for r in frame.receipts}
            self.assertEqual({"git", "braink-machine-image", "process"}, substrates)
            self.assertEqual({"OBSERVED"}, {r.status for r in frame.receipts})
            self.assertEqual("federated", frame.continuation["route"])

    def test_missing_machine_is_typed_unavailable_not_absent(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "missing.machine"
            federation = build_observer2_federation(machine_disk=missing, include_process=False)
            frame = federation.sample()
            self.assertEqual(1, len(frame.receipts))
            self.assertEqual("UNAVAILABLE", frame.receipts[0].status)
            self.assertTrue(frame.receipts[0].error)


if __name__ == "__main__":
    unittest.main(verbosity=2)
