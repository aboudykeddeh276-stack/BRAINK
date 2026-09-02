from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from enterprise.engineering_control_plane_r24 import (
    AppendOnlyLedger,
    MarketReadinessEvaluator,
    PromotionGate,
    ReconciliationEngine,
    ReleaseManifestBuilder,
    root,
)


@dataclass(frozen=True)
class WorkModule:
    module_id: str
    owner: str
    runtime: str
    dependencies: tuple[str, ...]
    invariants: tuple[str, ...]
    proof_ref: str
    rollback_ref: str
    frontage: str | None = None

    @property
    def module_root(self) -> str:
        return root(asdict(self))

    def validate(self) -> None:
        required = (self.module_id, self.owner, self.runtime, self.proof_ref, self.rollback_ref)
        if any(not value for value in required):
            raise ValueError("WORK_MODULE_IDENTITY_INCOMPLETE")
        if self.module_id in self.dependencies:
            raise ValueError("WORK_MODULE_SELF_DEPENDENCY")


@dataclass(frozen=True)
class AgentRole:
    role_id: str
    authority: str
    may_mutate: bool
    may_promote: bool


DEFAULT_AGENT_ROLES = (
    AgentRole("ARCHITECT", "design", False, False),
    AgentRole("IMPLEMENTER", "mutation", True, False),
    AgentRole("ADVERSARIAL_REVIEWER", "challenge", False, False),
    AgentRole("TEST_ENGINEER", "test", False, False),
    AgentRole("SECURITY_REVIEWER", "security", False, False),
    AgentRole("MARKET_QUALIFIER", "market", False, False),
    AgentRole("PROOF_VERIFIER", "promotion-proof", False, True),
)


class SuperagentOrchestrator:
    """Evidence-governed orchestration layer above the R24 engineering primitives."""

    def __init__(self, ledger_path: str | Path):
        self.ledger = AppendOnlyLedger(ledger_path)
        self.reconciliation = ReconciliationEngine()
        self.release_builder = ReleaseManifestBuilder()
        self.promotion_gate = PromotionGate()
        self.market = MarketReadinessEvaluator()
        self.modules: dict[str, WorkModule] = {}
        self.roles = {role.role_id: role for role in DEFAULT_AGENT_ROLES}

    def register_modules(self, modules: Iterable[WorkModule]) -> list[str]:
        admitted: list[str] = []
        for module in modules:
            module.validate()
            self.modules[module.module_id] = module
            self.ledger.append("MODULE_REGISTERED", module.module_id, {
                "module_root": module.module_root,
                "runtime": module.runtime,
                "owner": module.owner,
                "dependencies": list(module.dependencies),
            })
            admitted.append(module.module_id)
        return sorted(admitted)

    def unresolved_dependencies(self, module_id: str) -> list[str]:
        module = self.modules[module_id]
        return sorted(dep for dep in module.dependencies if dep not in self.modules)

    def runnable_modules(self) -> list[str]:
        return sorted(
            module_id for module_id in self.modules
            if not self.unresolved_dependencies(module_id)
        )

    def execute_work_module(
        self,
        *,
        module_id: str,
        actor_role: str,
        input_state: Mapping[str, Any],
        desired_state: Mapping[str, Any],
        mutation: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]],
        verifier: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]],
    ) -> dict[str, Any]:
        module = self.modules[module_id]
        role = self.roles[actor_role]
        if not role.may_mutate:
            raise PermissionError("ROLE_NOT_AUTHORIZED_TO_MUTATE")
        missing = self.unresolved_dependencies(module_id)
        if missing:
            raise RuntimeError(f"DEPENDENCY_UNRESOLVED:{','.join(missing)}")

        input_root = root(dict(input_state))
        checkpoint = {"state": dict(input_state), "state_root": input_root}
        output_state = dict(mutation(input_state, desired_state))
        verification = dict(verifier(output_state, desired_state))
        observed_equal = output_state == dict(desired_state)
        passed = observed_equal and verification.get("passed") is True

        receipt = self.ledger.append("WORK_MODULE_EXECUTED", module_id, {
            "actor_role": actor_role,
            "module_root": module.module_root,
            "input_root": input_root,
            "output_root": root(output_state),
            "desired_root": root(dict(desired_state)),
            "checkpoint": checkpoint,
            "verification": verification,
            "readback_equal": observed_equal,
            "status": "VERIFIED" if passed else "FAILED",
            "rollback_ref": module.rollback_ref,
        })
        return {
            "status": "VERIFIED" if passed else "FAILED",
            "output_state": output_state,
            "verification": verification,
            "receipt_root": receipt["record_root"],
            "rollback": checkpoint,
        }

    def reconcile_declared_observed(
        self,
        declared: Mapping[str, str],
        observed: Mapping[str, str],
    ) -> dict[str, Any]:
        result = self.reconciliation.reconcile(declared, observed)
        self.ledger.append("STATE_RECONCILED", "runtime://braink/r25", {
            "reconciliation_root": result["reconciliation_root"],
            "delta_count": result["delta_count"],
        })
        return result


def exact_mutation(_: Mapping[str, Any], desired: Mapping[str, Any]) -> Mapping[str, Any]:
    return dict(desired)


def exact_verifier(observed: Mapping[str, Any], desired: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "passed": dict(observed) == dict(desired),
        "observed_root": root(dict(observed)),
        "desired_root": root(dict(desired)),
    }
