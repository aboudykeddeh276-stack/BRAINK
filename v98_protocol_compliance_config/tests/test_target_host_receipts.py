from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from keddeh_target_host_receipts import (
    CommandResult,
    LOCAL_FAIL,
    LOCAL_PASS,
    TARGET_HOST_REQUIRED,
    collect_checks,
    run_target_host_receipts,
)


class TargetHostReceiptTests(unittest.TestCase):
    def successful_runner(self, command):
        command = list(command)
        if command[:2] == ["/bin/launchctl", "print"]:
            return CommandResult(command, 0, "service = com.keddeh.service-spine\nstate = running", "")
        if command and command[0] == "/usr/sbin/iostat":
            return CommandResult(
                command,
                0,
                "disk0       KB/t  tps  MB/s\n            12.00  10  0.12  1.0\n",
                "",
            )
        return CommandResult(command, 127, "", "unexpected command")

    def test_m3_runner_receipt_requires_real_launchd_and_iostat_readback(self) -> None:
        environment = {
            "GITHUB_ACTIONS": "true",
            "RUNNER_ENVIRONMENT": "self-hosted",
            "RUNNER_OS": "macOS",
            "RUNNER_ARCH": "ARM64",
            "RUNNER_NAME": "Aboudys-M3",
            "GITHUB_RUN_ID": "123",
            "GITHUB_SHA": "abc",
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = run_target_host_receipts(
                Path(tmp),
                emit_receipt=True,
                command_runner=self.successful_runner,
                environ=environment,
                system="Darwin",
                machine="arm64",
                uid=501,
            )
            self.assertTrue(result["all_required_checks_passed"])
            self.assertTrue(result["ledger_readback"])
            self.assertEqual(result["classification_counts"].get(LOCAL_PASS), 5)
            self.assertTrue((Path(tmp) / "evidence" / "target_host_receipts.json").exists())
            self.assertTrue(Path(result["outbox_manifest"]).exists())

    def test_missing_launchd_service_fails_closed(self) -> None:
        def runner(command):
            command = list(command)
            if command[:2] == ["/bin/launchctl", "print"]:
                return CommandResult(command, 113, "", "Could not find service")
            return self.successful_runner(command)

        checks = collect_checks(
            command_runner=runner,
            environ={
                "GITHUB_ACTIONS": "true",
                "RUNNER_ENVIRONMENT": "self-hosted",
                "RUNNER_OS": "macOS",
                "RUNNER_ARCH": "ARM64",
            },
            system="Darwin",
            machine="arm64",
            uid=501,
        )
        by_id = {check.check_id: check for check in checks}
        self.assertEqual(by_id["launchd_service"].status, LOCAL_FAIL)
        self.assertFalse(by_id["launchd_service"].metrics.get("stdout"))

    def test_non_macos_runtime_stays_target_host_required(self) -> None:
        commands = []

        def runner(command):
            commands.append(list(command))
            return CommandResult(list(command), 0, "", "")

        checks = collect_checks(
            command_runner=runner,
            environ={},
            system="Linux",
            machine="x86_64",
            uid=1000,
        )
        by_id = {check.check_id: check for check in checks}
        self.assertEqual(by_id["runner_context"].status, TARGET_HOST_REQUIRED)
        self.assertEqual(by_id["launchd_service"].status, TARGET_HOST_REQUIRED)
        self.assertEqual(by_id["iostat_sample"].status, TARGET_HOST_REQUIRED)
        self.assertEqual(commands, [])


if __name__ == "__main__":
    unittest.main()
