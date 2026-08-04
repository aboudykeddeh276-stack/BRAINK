from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from src.keddeh_persisted_export_service import ExportContractError, PersistedExportService, sha256_file


class PersistedExportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "runtime_volume" / "cases" / "CASE-1").mkdir(parents=True)
        self.record = self.root / "runtime_volume" / "cases" / "CASE-1" / "case-record.json"
        self.report = self.root / "runtime_volume" / "cases" / "CASE-1" / "report.md"
        self.record.write_text('{"case_id":"CASE-1","state":"persisted"}\n', encoding="utf-8")
        self.report.write_text("# Case report\nPersisted source.\n", encoding="utf-8")
        self.service = PersistedExportService(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_complete_export_writes_download_receipt_ledger_and_outbox(self) -> None:
        receipt = self.service.create_export(
            "CASE-1",
            [self.record.relative_to(self.root), self.report.relative_to(self.root)],
            "CASE-1-complete-export.zip",
        )
        archive = self.root / receipt.archive_path
        self.assertTrue(archive.is_file())
        self.assertEqual("application/zip", receipt.content_type)
        self.assertEqual("CASE-1-complete-export.zip", receipt.attachment_filename)
        self.assertEqual(2, receipt.source_count)
        self.assertTrue(receipt.zip_integrity_passed)
        self.assertTrue(receipt.source_byte_readback_passed)
        self.assertTrue(receipt.persisted_storage_passed)
        self.assertTrue(receipt.ledger_readback_passed)
        self.assertEqual(receipt.archive_sha256, sha256_file(archive))

        with zipfile.ZipFile(archive) as bundle:
            self.assertIsNone(bundle.testzip())
            self.assertEqual(self.record.read_bytes(), bundle.read("runtime_volume/cases/CASE-1/case-record.json"))
            self.assertEqual(self.report.read_bytes(), bundle.read("runtime_volume/cases/CASE-1/report.md"))
            manifest = json.loads(bundle.read("SHA256-MANIFEST.json"))
            self.assertEqual(2, len(manifest["sources"]))

        outbox = json.loads((self.root / receipt.outbox_handoff_path).read_text(encoding="utf-8"))
        self.assertEqual("READY_FOR_DOWNLOAD", outbox["state"])
        self.assertEqual('attachment; filename="CASE-1-complete-export.zip"', outbox["attachment"]["content_disposition"])
        ledger = [json.loads(line) for line in (self.root / "runtime_volume" / "proof_bundles.ledger").read_text(encoding="utf-8").splitlines()]
        self.assertTrue(any(row["export_id"] == "CASE-1" and row["archive_sha256"] == receipt.archive_sha256 for row in ledger))

    def test_missing_source_fails_without_advertising_download(self) -> None:
        with self.assertRaises(ExportContractError):
            self.service.create_export("missing", [Path("runtime_volume/cases/missing.json")])
        self.assertFalse((self.root / "exports" / "downloads" / "missing-complete-export.zip").exists())

    def test_path_escape_is_rejected(self) -> None:
        outside = Path(self.temp.name).parent / "outside-export-source.txt"
        outside.write_text("outside", encoding="utf-8")
        try:
            with self.assertRaises(ExportContractError):
                self.service.create_export("escape", [outside])
        finally:
            outside.unlink(missing_ok=True)

    def test_empty_export_is_rejected(self) -> None:
        with self.assertRaises(ExportContractError):
            self.service.create_export("empty", [])

    def test_invalid_attachment_filename_is_rejected(self) -> None:
        with self.assertRaises(ExportContractError):
            self.service.create_export("CASE-1", [self.record], "../case.zip")
        with self.assertRaises(ExportContractError):
            self.service.create_export("CASE-1", [self.record], "case.json")

    def test_source_change_after_export_fails_byte_readback(self) -> None:
        receipt = self.service.create_export("CASE-1", [self.record])
        archive = self.root / receipt.archive_path
        self.record.write_text('{"case_id":"CASE-1","state":"changed"}\n', encoding="utf-8")
        zip_ok, bytes_ok = self.service.verify_export(archive)
        self.assertTrue(zip_ok)
        self.assertFalse(bytes_ok)

    def test_corrupt_zip_fails_integrity(self) -> None:
        receipt = self.service.create_export("CASE-1", [self.record])
        archive = self.root / receipt.archive_path
        archive.write_bytes(b"not-a-zip")
        self.assertEqual((False, False), self.service.verify_export(archive))


if __name__ == "__main__":
    unittest.main()
