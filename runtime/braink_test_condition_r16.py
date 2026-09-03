from dataclasses import dataclass, asdict
import json
from pathlib import Path

@dataclass
class GateObservation:
    layer: str
    production_effect: str
    test_effect: str
    reason: str

class BrainkTestConditionR16:
    def __init__(self, mode: str):
        if mode not in {"TEST", "PRODUCTION"}:
            raise ValueError("mode must be TEST or PRODUCTION")
        self.mode = mode

    def evaluate(self, operation: str, has_authority: bool, security_allows: bool):
        observations = [
            GateObservation("AUTHORITY", "ALLOW" if has_authority else "BLOCK", "OBSERVE_ONLY", "Authority is not a prerequisite for exercising a testing condition."),
            GateObservation("SECURITY", "ALLOW" if security_allows else "BLOCK", "OBSERVE_ONLY", "Security policy is a separate production-control plane from test execution."),
        ]
        if self.mode == "TEST":
            executed = True
            blocked_by = []
        else:
            blocked_by = []
            if not has_authority:
                blocked_by.append("AUTHORITY")
            if not security_allows:
                blocked_by.append("SECURITY")
            executed = not blocked_by
        return {
            "schema": "braink.test-condition.r16",
            "mode": self.mode,
            "operation": operation,
            "executed": executed,
            "blocked_by": blocked_by,
            "observations": [asdict(x) for x in observations],
            "promotion_rule": "TEST_PASS_PROVES_TEST_BEHAVIOR_ONLY; PRODUCTION_AUTHORITY_AND_SECURITY_REQUIRE_SEPARATE_PROOF",
        }

if __name__ == "__main__":
    test = BrainkTestConditionR16("TEST").evaluate("PUBLIC_DNS_RDAP_TLS_HTTPS_OBSERVATION", False, False)
    prod = BrainkTestConditionR16("PRODUCTION").evaluate("PUBLIC_DNS_RDAP_TLS_HTTPS_OBSERVATION", False, False)
    receipt = {
        "test_case": test,
        "production_control_case": prod,
        "checks": {
            "test_executes_without_authority": test["executed"] is True,
            "test_executes_despite_security_gate": test["executed"] is True,
            "production_still_blocks_without_authority_security": prod["executed"] is False,
            "planes_separated": test["blocked_by"] == [] and set(prod["blocked_by"]) == {"AUTHORITY", "SECURITY"},
        },
    }
    receipt["status"] = "PASS" if all(receipt["checks"].values()) else "FAIL"
    Path("/mnt/data/BRAINK_R16_TEST_CONDITION_SEPARATION_RECEIPT.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
