#!/usr/bin/env python3
"""
BRAINK System Health Check and Deployment Verification

This script performs comprehensive validation of the BRAINK system including:
- Governance artifact verification
- Manifest integrity checking
- Route coverage analysis
- Error context configuration validation
- Dead route registry verification
- End-to-end system smoke testing
"""

import json
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class BRAINKHealthCheck:
    def __init__(self, root_path: str = "."):
        self.root = Path(root_path)
        self.results = {}
        self.errors = []
        self.warnings = []
        self.passed_checks = 0
        self.failed_checks = 0

    def log_check(self, name: str, passed: bool, message: str = ""):
        """Log a health check result."""
        status = "✓" if passed else "✗"
        print(f"{status} {name}")
        if message:
            print(f"  {message}")
        
        if passed:
            self.passed_checks += 1
        else:
            self.failed_checks += 1
            self.errors.append((name, message))

    def check_governance_artifacts(self) -> bool:
        """Verify all required governance artifacts exist."""
        print("\n" + "=" * 60)
        print("GOVERNANCE ARTIFACT VERIFICATION")
        print("=" * 60)
        
        required_files = [
            "README.md",
            "LICENSE",
            ".gitignore",
            "docs/governance/repository-governance-standard.md",
            "docs/governance/agentic-intelligence-cli.md",
            "docs/governance/strict-deep-analysis-comment.md",
            "docs/governance/zero-less-governance.md",
            "docs/governance/manifest.json",
            "scripts/validate-governance.py",
            "scripts/braink-agent-cli.py",
        ]
        
        all_exist = True
        for file_path in required_files:
            full_path = self.root / file_path
            exists = full_path.exists()
            self.log_check(
                f"Artifact: {file_path}",
                exists,
                "" if exists else "MISSING"
            )
            all_exist = all_exist and exists
        
        return all_exist

    def check_manifest_integrity(self) -> bool:
        """Verify manifest artifact hashes."""
        print("\n" + "=" * 60)
        print("MANIFEST INTEGRITY VERIFICATION")
        print("=" * 60)
        
        manifest_path = self.root / "docs/governance/manifest.json"
        
        if not manifest_path.exists():
            self.log_check("Manifest exists", False, "manifest.json not found")
            return False
        
        self.log_check("Manifest exists", True)
        
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            
            self.log_check("Manifest is valid JSON", True)
        except Exception as e:
            self.log_check("Manifest is valid JSON", False, str(e))
            return False
        
        # Verify artifacts (skip self-reference)
        verified = 0
        total = 0
        
        for artifact_key, artifact_info in sorted(manifest.items()):
            if artifact_key == "ARTIFACT_DOCS_GOVERNANCE_MANIFEST_JSON":
                continue  # Skip self-reference (known limitation)
            
            total += 1
            path = artifact_info['path']
            expected_sha = artifact_info['sha256']
            full_path = self.root / path
            
            if not full_path.exists():
                self.log_check(f"  Artifact: {path}", False, "FILE NOT FOUND")
                continue
            
            try:
                with open(full_path, 'rb') as f:
                    actual_sha = hashlib.sha256(f.read()).hexdigest()
                
                matches = actual_sha == expected_sha
                self.log_check(
                    f"  Artifact: {path}",
                    matches,
                    "" if matches else f"HASH MISMATCH"
                )
                
                if matches:
                    verified += 1
            except Exception as e:
                self.log_check(f"  Artifact: {path}", False, str(e))
        
        print(f"\nArtifact Verification: {verified}/{total} verified")
        return verified == total

    def check_zero_less_governance(self) -> bool:
        """Verify zero-less governance implementation."""
        print("\n" + "=" * 60)
        print("ZERO-LESS GOVERNANCE VERIFICATION")
        print("=" * 60)
        
        governance_file = self.root / "NativeChatBot/Sources/ZeroLessGovernance.swift"
        
        if not governance_file.exists():
            self.log_check("ZeroLessGovernance.swift exists", False)
            return False
        
        self.log_check("ZeroLessGovernance.swift exists", True)
        
        with open(governance_file, 'r') as f:
            content = f.read()
        
        # Check for required components
        checks = [
            ("ZeroLessIndex enum", "enum ZeroLessIndex"),
            ("stateNeg3 = -3", "stateNeg3 = -3"),
            ("stateNeg2 = -2", "stateNeg2 = -2"),
            ("observerSingular1 = 1", "observerSingular1 = 1"),
            ("statePos2 = 2", "statePos2 = 2"),
            ("statePos3 = 3", "statePos3 = 3"),
            ("BRAINKRouteIdentifier enum", "enum BRAINKRouteIdentifier"),
            ("validate function", "static func validate"),
            ("hardwareSlot function", "static func hardwareSlot"),
        ]
        
        for check_name, pattern in checks:
            present = pattern in content
            self.log_check(f"  {check_name}", present)
        
        return all(pattern in content for _, pattern in checks)

    def check_error_context(self) -> bool:
        """Verify error context implementation."""
        print("\n" + "=" * 60)
        print("ERROR CONTEXT VERIFICATION")
        print("=" * 60)
        
        error_file = self.root / "NativeChatBot/Sources/ErrorContext.swift"
        
        if not error_file.exists():
            self.log_check("ErrorContext.swift exists", False)
            return False
        
        self.log_check("ErrorContext.swift exists", True)
        
        with open(error_file, 'r') as f:
            content = f.read()
        
        # Check for required components
        checks = [
            ("BRAINKErrorSector enum", "enum BRAINKErrorSector"),
            ("BRAINKFailureCause enum", "enum BRAINKFailureCause"),
            ("BRAINKErrorContext struct", "struct BRAINKErrorContext"),
            ("BRAINKErrorContextFactory", "enum BRAINKErrorContextFactory"),
            ("make factory function", "static func make"),
            ("toCompactString function", "static func toCompactString"),
        ]
        
        for check_name, pattern in checks:
            present = pattern in content
            self.log_check(f"  {check_name}", present)
        
        return all(pattern in content for _, pattern in checks)

    def check_dead_route_registry(self) -> bool:
        """Verify dead route registry."""
        print("\n" + "=" * 60)
        print("DEAD ROUTE REGISTRY VERIFICATION")
        print("=" * 60)
        
        registry_file = self.root / "NativeChatBot/Sources/DeadRouteRegistry.swift"
        
        if not registry_file.exists():
            self.log_check("DeadRouteRegistry.swift exists", False)
            return False
        
        self.log_check("DeadRouteRegistry.swift exists", True)
        
        with open(registry_file, 'r') as f:
            content = f.read()
        
        # Check for required components
        checks = [
            ("DeadRouteResolution struct", "struct DeadRouteResolution"),
            ("DeadRouteRegistry enum", "enum DeadRouteRegistry"),
            ("claudeAPIv1 route", "claudeAPIv1"),
            ("resolve function", "static func resolve"),
        ]
        
        for check_name, pattern in checks:
            present = pattern in content
            self.log_check(f"  {check_name}", present)
        
        return all(pattern in content for _, pattern in checks)

    def check_smoke_tests(self) -> bool:
        """Run smoke tests."""
        print("\n" + "=" * 60)
        print("SMOKE TEST EXECUTION")
        print("=" * 60)
        
        smoke_test = self.root / "NativeChatBot/run-runtime-smoke.command"
        
        if not smoke_test.exists():
            self.log_check("Smoke test script exists", False)
            return False
        
        self.log_check("Smoke test script exists", True)
        
        try:
            result = subprocess.run(
                ["bash", str(smoke_test)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self.root)
            )
            
            output = result.stdout + result.stderr
            
            checks = [
                ("SMOKE_STATUS: DONE", "SMOKE_STATUS: DONE" in output),
                ("SMOKE_ROUTES present", "SMOKE_ROUTES:" in output),
                ("SMOKE_AUDIT_OUTCOME: DONE", "SMOKE_AUDIT_OUTCOME: DONE" in output),
                ("Alignment score", "SMOKE_AUDIT_ALIGNMENT: 1.0000" in output),
            ]
            
            for check_name, passed in checks:
                self.log_check(f"  {check_name}", passed)
            
            return all(passed for _, passed in checks)
            
        except subprocess.TimeoutExpired:
            self.log_check("  Smoke tests execute", False, "TIMEOUT")
            return False
        except Exception as e:
            self.log_check("  Smoke tests execute", False, str(e))
            return False

    def check_governance_scripts(self) -> bool:
        """Verify governance validation scripts."""
        print("\n" + "=" * 60)
        print("GOVERNANCE SCRIPTS VERIFICATION")
        print("=" * 60)
        
        try:
            # Check governance validation
            result = subprocess.run(
                ["python3", "scripts/validate-governance.py"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.root)
            )
            
            governance_ok = "GOVERNANCE_CHECK_STATUS: COMPLETED" in result.stdout
            self.log_check("  validate-governance.py", governance_ok)
            
            # Check agent CLI
            result = subprocess.run(
                ["python3", "scripts/braink-agent-cli.py", "status"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.root)
            )
            
            agent_ok = "BRAINK_AGENT_CLI_STATUS: COMPLETED" in result.stdout
            self.log_check("  braink-agent-cli.py status", agent_ok)
            
            # Check ethics check
            result = subprocess.run(
                ["python3", "tools/kex_ethics_check.py", "--root", ".", "--output", "reports/kex_ethics_check.json"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.root)
            )
            
            ethics_ok = "KEX_ETHICS_CHECK" in result.stdout and "status=COMPLETED" in result.stdout
            self.log_check("  kex_ethics_check.py", ethics_ok)
            
            return governance_ok and agent_ok and ethics_ok
            
        except Exception as e:
            self.log_check("  Governance scripts", False, str(e))
            return False

    def check_documentation(self) -> bool:
        """Verify documentation completeness."""
        print("\n" + "=" * 60)
        print("DOCUMENTATION VERIFICATION")
        print("=" * 60)
        
        checks = [
            ("README.md", self.root / "README.md"),
            ("NativeChatBot/README.md", self.root / "NativeChatBot/README.md"),
            ("Zero-less governance docs", self.root / "docs/governance/zero-less-governance.md"),
            ("Repository governance standard", self.root / "docs/governance/repository-governance-standard.md"),
        ]
        
        all_good = True
        for check_name, doc_path in checks:
            exists = doc_path.exists()
            self.log_check(f"  {check_name}", exists)
            all_good = all_good and exists
        
        return all_good

    def run_all_checks(self) -> Tuple[int, int]:
        """Run all health checks."""
        print("\n" + "=" * 70)
        print("BRAINK SYSTEM HEALTH CHECK - COMPREHENSIVE VERIFICATION")
        print("=" * 70)
        
        self.check_governance_artifacts()
        self.check_manifest_integrity()
        self.check_zero_less_governance()
        self.check_error_context()
        self.check_dead_route_registry()
        self.check_governance_scripts()
        self.check_documentation()
        self.check_smoke_tests()
        
        return self.passed_checks, self.failed_checks

    def print_summary(self):
        """Print health check summary."""
        print("\n" + "=" * 70)
        print("HEALTH CHECK SUMMARY")
        print("=" * 70)
        
        print(f"\n✓ Passed: {self.passed_checks}")
        print(f"✗ Failed: {self.failed_checks}")
        
        if self.errors:
            print(f"\nErrors ({len(self.errors)}):")
            for name, message in self.errors:
                print(f"  ✗ {name}: {message}")
        
        if self.warnings:
            print(f"\nWarnings ({len(self.warnings)}):")
            for name, message in self.warnings:
                print(f"  ⚠ {name}: {message}")
        
        print("\n" + "=" * 70)
        if self.failed_checks == 0:
            print("✓ ALL HEALTH CHECKS PASSED - SYSTEM READY FOR DEPLOYMENT")
        else:
            print(f"✗ {self.failed_checks} CHECKS FAILED - PLEASE REVIEW ABOVE")
        print("=" * 70 + "\n")


def main():
    """Main entry point."""
    root_path = sys.argv[1] if len(sys.argv) > 1 else "."
    
    checker = BRAINKHealthCheck(root_path)
    passed, failed = checker.run_all_checks()
    checker.print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
