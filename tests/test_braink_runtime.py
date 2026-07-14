#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


braink_cli = load_module("braink_agent_cli", "scripts/braink-agent-cli.py")
self_sustain = load_module("kex_self_sustain", "tools/kex_self_sustain.py")
ethics = load_module("kex_ethics_check", "tools/kex_ethics_check.py")


class GitRepoMixin:
    def init_repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, stdout=subprocess.PIPE)
        subprocess.run(["git", "config", "user.email", "braink-test@local.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "BRAINK Test"], cwd=root, check=True)

    def commit_all(self, root: Path) -> None:
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "fixture"], cwd=root, check=True, stdout=subprocess.PIPE)


class BrainkAgentCliTests(unittest.TestCase, GitRepoMixin):
    def test_clean_repository_is_not_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_repo(root)
            for relative in braink_cli.GOVERNANCE_FILES:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"fixture:{relative}\n", encoding="utf-8")
            self.commit_all(root)

            signal = braink_cli.inspect_repository(root)
            self.assertFalse(signal.dirty)
            self.assertEqual(signal.state, "STATE_MODEL_LOCAL")
            self.assertEqual(signal.governance_files_missing, [])

    def test_modified_repository_is_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_repo(root)
            (root / "README.md").write_text("initial\n", encoding="utf-8")
            self.commit_all(root)
            (root / "README.md").write_text("changed\n", encoding="utf-8")
            self.assertTrue(braink_cli.inspect_repository(root).dirty)

    def test_missing_scan_root_is_rejected(self) -> None:
        missing = Path(tempfile.gettempdir()) / "braink-definitely-missing-root"
        self.assertRaises(ValueError, braink_cli.discover_repositories, missing)


class SelfSustainTests(unittest.TestCase, GitRepoMixin):
    def test_packet_verifies_complete_file_set_then_rejects_new_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_repo(root)
            (root / "README.md").write_text("proof_packet runtime_trace\n", encoding="utf-8")
            (root / "app.py").write_text("print('BRAINK')\n", encoding="utf-8")
            self.commit_all(root)

            packet = self_sustain.build_packet(
                root,
                "fixture",
                generated_at="2026-07-14T00:00:00+00:00",
            )
            json_path, _ = self_sustain.write_packet(packet, root / "reports", "fixture")
            self.assertEqual(self_sustain.verify_packet(json_path, root), [])

            (root / "new_module.py").write_text("print('new')\n", encoding="utf-8")
            errors = self_sustain.verify_packet(json_path, root)
            self.assertTrue(any(error.startswith("file_count_mismatch:") for error in errors))
            self.assertIn("unlisted_artifact:new_module.py", errors)

    def test_route_scanner_does_not_prove_its_own_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scanner = root / "tools" / "kex_self_sustain.py"
            scanner.parent.mkdir(parents=True)
            scanner.write_text(" ".join(self_sustain.ROUTE_TOKENS), encoding="utf-8")
            coverage = self_sustain.route_coverage(root)
            self.assertEqual(set(coverage.values()), {"PENDING"})

    def test_same_basename_repositories_receive_unique_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            left = root / "left" / "same"
            right = root / "right" / "same"
            left.mkdir(parents=True)
            right.mkdir(parents=True)
            self.assertNotEqual(
                self_sustain.packet_token(left, root, True),
                self_sustain.packet_token(right, root, True),
            )

    def test_missing_root_is_rejected(self) -> None:
        missing = Path(tempfile.gettempdir()) / "kex-definitely-missing-root"
        self.assertRaises(ValueError, self_sustain.require_directory, missing, "root")


class EthicsCheckerTests(unittest.TestCase):
    def test_relative_manifest_and_output_resolve_under_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "kex" / "kex_affect_ethics_model.json"
            manifest_path.parent.mkdir(parents=True)
            manifest = {
                "token": "KEX_AFFECT_RESPONSE_VALID",
                "anchor": "A. KEDDEH / BRAINK / KEX",
                "status": "MODEL-LOCAL",
                "boundary": "Local boundary model.",
                "ethical_impact_predicate": [
                    "SafetyPreserved", "AgencyPreserved", "ConsentRespected",
                    "NoManipulativeEscalation", "UncertaintyDeclared",
                    "RepairRouteAvailable", "NoUnsupportedBioClaim",
                ],
                "response_gate": [
                    "HumanBioBoundaryPreserved", "CodexNonBiologicalBoundaryPreserved",
                    "BRAINKAnchorPreserved", "NoManipulation", "NoUnsupportedMedicalClaim",
                    "RepairRouteAvailable", "BlockersPreserved",
                ],
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            (root / "README.md").write_text("bounded local fixture\n", encoding="utf-8")

            result = ethics.main([
                "--root", str(root),
                "--output", "reports/ethics.json",
                "--generated-at", "2026-07-14T00:00:00+00:00",
            ])
            self.assertEqual(result, 0)
            report = json.loads((root / "reports" / "ethics.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "COMPLETED")
            self.assertEqual(Path(report["manifest"]), manifest_path.resolve())


if __name__ == "__main__":
    unittest.main()
