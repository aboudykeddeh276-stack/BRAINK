#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


class ExportContractError(RuntimeError):
    """Raised when an export cannot satisfy the persisted-download contract."""


@dataclass(frozen=True)
class ExportReceipt:
    export_id: str
    archive_path: str
    attachment_filename: str
    content_type: str
    source_count: int
    archive_sha256: str
    manifest_sha256: str
    zip_integrity_passed: bool
    source_byte_readback_passed: bool
    persisted_storage_passed: bool
    ledger_readback_passed: bool
    outbox_handoff_path: str
    created_at: float


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


class PersistedExportService:
    """Create downloadable ZIPs from persisted source data with executable readback.

    The service never advertises a scratch path as a durable download. Sources must be
    regular, non-symlink files beneath the configured repository root. The resulting ZIP
    is written beneath ``exports/downloads``, reopened, CRC-tested, byte-compared against
    every source, recorded in the proof ledger, read back from that ledger and handed off
    through a replayable outbox envelope.
    """

    CONTENT_TYPE = "application/zip"

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.download_dir = self.root / "exports" / "downloads"
        self.receipt_dir = self.root / "evidence" / "exports"
        self.outbox_dir = self.root / "runtime_volume" / "outbox" / "persisted_exports"
        self.ledger_path = self.root / "runtime_volume" / "proof_bundles.ledger"

    def _validated_sources(self, sources: Iterable[Path]) -> list[Path]:
        validated: list[Path] = []
        seen: set[Path] = set()
        for source in sources:
            candidate = source if source.is_absolute() else self.root / source
            unresolved = candidate.expanduser()
            if unresolved.is_symlink():
                raise ExportContractError(f"symlink source prohibited: {source}")
            resolved = unresolved.resolve()
            try:
                resolved.relative_to(self.root)
            except ValueError as exc:
                raise ExportContractError(f"source escapes persisted root: {source}") from exc
            if not resolved.is_file():
                raise ExportContractError(f"source is not a readable regular file: {source}")
            if resolved in seen:
                raise ExportContractError(f"duplicate source: {source}")
            seen.add(resolved)
            validated.append(resolved)
        if not validated:
            raise ExportContractError("at least one persisted source file is required")
        return sorted(validated, key=lambda item: item.relative_to(self.root).as_posix())

    def create_export(self, export_id: str, sources: Sequence[Path], attachment_filename: str | None = None) -> ExportReceipt:
        if not export_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for char in export_id):
            raise ExportContractError("export_id must contain only letters, digits, dash, underscore or dot")
        validated = self._validated_sources(sources)
        filename = attachment_filename or f"{export_id}-complete-export.zip"
        if Path(filename).name != filename or not filename.lower().endswith(".zip"):
            raise ExportContractError("attachment filename must be a basename ending in .zip")

        self.download_dir.mkdir(parents=True, exist_ok=True)
        archive = self.download_dir / filename
        temporary = archive.with_suffix(archive.suffix + ".partial")
        if temporary.exists():
            temporary.unlink()

        source_entries = [
            {
                "path": path.relative_to(self.root).as_posix(),
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
            for path in validated
        ]
        manifest = {
            "schema": "keddeh.persisted-export.v1",
            "export_id": export_id,
            "attachment_filename": filename,
            "content_type": self.CONTENT_TYPE,
            "sources": source_entries,
        }
        manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")

        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                for source in validated:
                    bundle.write(source, source.relative_to(self.root).as_posix())
                bundle.writestr("SHA256-MANIFEST.json", manifest_bytes)
            os.replace(temporary, archive)
        finally:
            if temporary.exists():
                temporary.unlink()

        zip_ok, bytes_ok = self.verify_export(archive, manifest)
        if not zip_ok or not bytes_ok:
            archive.unlink(missing_ok=True)
            raise ExportContractError("archive failed ZIP integrity or source byte readback")

        archive_hash = sha256_file(archive)
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        created_at = time.time()
        receipt_path = self.receipt_dir / f"{export_id}.receipt.json"
        outbox_path = self.outbox_dir / f"{export_id}.handoff.json"
        ledger_entry = {
            "event": "PERSISTED_EXPORT_AVAILABLE",
            "export_id": export_id,
            "archive_path": archive.relative_to(self.root).as_posix(),
            "archive_sha256": archive_hash,
            "attachment_filename": filename,
            "content_type": self.CONTENT_TYPE,
            "created_at": created_at,
        }
        append_jsonl(self.ledger_path, ledger_entry)
        ledger_readback = any(
            json.loads(line).get("export_id") == export_id and json.loads(line).get("archive_sha256") == archive_hash
            for line in self.ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        if not ledger_readback:
            raise ExportContractError("proof ledger readback failed")

        handoff = {
            "schema": "keddeh.persisted-export-handoff.v1",
            "state": "READY_FOR_DOWNLOAD",
            "export_id": export_id,
            "archive_path": archive.relative_to(self.root).as_posix(),
            "attachment": {
                "filename": filename,
                "content_type": self.CONTENT_TYPE,
                "content_disposition": f'attachment; filename="{filename}"',
            },
            "archive_sha256": archive_hash,
            "replay_policy": "serve persisted archive only after hash and ZIP readback",
            "created_at": created_at,
        }
        write_json(outbox_path, handoff)

        receipt = ExportReceipt(
            export_id=export_id,
            archive_path=archive.relative_to(self.root).as_posix(),
            attachment_filename=filename,
            content_type=self.CONTENT_TYPE,
            source_count=len(validated),
            archive_sha256=archive_hash,
            manifest_sha256=manifest_hash,
            zip_integrity_passed=zip_ok,
            source_byte_readback_passed=bytes_ok,
            persisted_storage_passed=archive.is_file() and archive.parent == self.download_dir,
            ledger_readback_passed=ledger_readback,
            outbox_handoff_path=outbox_path.relative_to(self.root).as_posix(),
            created_at=created_at,
        )
        write_json(receipt_path, asdict(receipt))
        return receipt

    def verify_export(self, archive: Path, manifest: dict[str, Any] | None = None) -> tuple[bool, bool]:
        if not archive.is_file() or archive.is_symlink():
            return False, False
        try:
            with zipfile.ZipFile(archive, "r") as bundle:
                zip_ok = bundle.testzip() is None
                loaded_manifest = manifest or json.loads(bundle.read("SHA256-MANIFEST.json"))
                for entry in loaded_manifest.get("sources", []):
                    source = (self.root / entry["path"]).resolve()
                    try:
                        source.relative_to(self.root)
                    except ValueError:
                        return zip_ok, False
                    if not source.is_file() or source.is_symlink():
                        return zip_ok, False
                    archived_bytes = bundle.read(entry["path"])
                    if hashlib.sha256(archived_bytes).hexdigest() != entry["sha256"]:
                        return zip_ok, False
                    if archived_bytes != source.read_bytes():
                        return zip_ok, False
                return zip_ok, True
        except (OSError, KeyError, ValueError, zipfile.BadZipFile, json.JSONDecodeError):
            return False, False


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a persisted, receipt-backed downloadable ZIP")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--export-id", required=True)
    parser.add_argument("--attachment-filename")
    parser.add_argument("sources", nargs="+", type=Path)
    args = parser.parse_args()
    receipt = PersistedExportService(args.root).create_export(args.export_id, args.sources, args.attachment_filename)
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
