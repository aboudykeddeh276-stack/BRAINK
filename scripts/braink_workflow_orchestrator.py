#!/usr/bin/env python3
"""BRAINK-native GitHub Actions workflow orchestration.

This script replaces external AI workflow routing with BRAINK's repository-local
execution flow. It plans deterministic routes, validates the runtime/auth
configuration, runs proof-bound repository commands, and emits an audit report
for GitHub Actions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INTENT = (
    "software that can code using my software and task it to each repo "
    "using my self existence design"
)
ALIGNMENT_TOLERANCE = 1e-9

ROUTE_ORDER = [
    "auth",
    "self_sustained_coder",
    "kex_hyperdrive",
    "proof_packet",
    "stack_audit",
]

ROUTE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("auth", ("auth", "oauth", "login")),
    (
        "self_sustained_coder",
        (
            "self sustained coder",
            "self-sustained coder",
            "software that can code",
            "task it to each repo",
            "self existence design",
            "code generation",
        ),
    ),
    (
        "kex_hyperdrive",
        (
            "kex hyperdrive",
            "state of transition",
            "transition of state",
            "definition of transition",
            "transition of definitions",
            "definition of state",
            "state of definitions",
            "x of x of x of x",
            "calibration analysis",
            "repo calibration",
        ),
    ),
    ("proof_packet", ("proof", "proof packet", "proof-packet", "falsifier")),
    (
        "stack_audit",
        ("stack audit", "alignment", "module alignment", "line for line proof"),
    ),
]

ALLOWED_COMMANDS: dict[str, list[str]] = {
    "governance_check": ["python3", "scripts/validate-governance.py"],
    "self_sustain_generate": [
        "python3",
        "tools/kex_self_sustain.py",
        "--root",
        ".",
        "--output-dir",
        "reports",
    ],
    "self_sustain_verify": [
        "python3",
        "tools/kex_self_sustain.py",
        "--root",
        ".",
        "--verify-packet",
        "reports/BRAINK_kex_self_sustain_packet.json",
    ],
    "ethics_check": [
        "python3",
        "tools/kex_ethics_check.py",
        "--root",
        ".",
        "--output",
        "reports/kex_ethics_check.json",
    ],
    "runtime_smoke": ["./NativeChatBot/run-runtime-smoke.command"],
}


@dataclass
class RoutePlan:
    intent: str
    routes: list[str]
    route_reasoning: dict[str, str]
    runtime_mode: str
    runtime_endpoint: str
    fallback_reason: str | None
    auth_configured: bool
    knowledge_center_runtime_path: str
    execution_policy: dict[str, Any]


@dataclass
class StepResult:
    name: str
    command: list[str]
    returncode: int
    status: str
    log_path: str
    markers: dict[str, Any]



def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())



def classify_routes(intent: str) -> tuple[list[str], dict[str, str]]:
    lower = normalized(intent)
    selected: list[str] = []
    reasoning: dict[str, str] = {}

    for route, keywords in ROUTE_KEYWORDS:
        for keyword in keywords:
            if keyword in lower:
                if route not in selected:
                    selected.append(route)
                    reasoning[route] = f"matched keyword: {keyword}"
                break

    if "self_sustained_coder" not in selected:
        selected.insert(0, "self_sustained_coder")
        reasoning.setdefault("self_sustained_coder", "default BRAINK code-generation route")
    if "kex_hyperdrive" not in selected:
        insert_at = 1 if selected and selected[0] == "self_sustained_coder" else 0
        selected.insert(insert_at, "kex_hyperdrive")
        reasoning.setdefault("kex_hyperdrive", "paired repository calibration route")
    for route, reason in (
        ("proof_packet", "proof packet required for route evidence"),
        ("stack_audit", "stack audit required for alignment verification"),
    ):
        if route not in selected:
            selected.append(route)
            reasoning.setdefault(route, reason)

    ordered = [route for route in ROUTE_ORDER if route in selected]
    return ordered, reasoning



def auth_state(env: dict[str, str]) -> tuple[bool, dict[str, str]]:
    portal = env.get("EXPO_PUBLIC_OAUTH_PORTAL_URL", "").strip()
    server = env.get("EXPO_PUBLIC_OAUTH_SERVER_URL", "").strip()
    api_base = env.get("EXPO_PUBLIC_API_BASE_URL", "").strip()
    app_id = env.get("EXPO_PUBLIC_APP_ID", "").strip()
    configured = bool(portal and app_id and (server or api_base))
    details = {
        "portal": "set" if portal else "missing",
        "server": "set" if server else "missing",
        "api_base": "set" if api_base else "missing",
        "app_id": "set" if app_id else "missing",
    }
    return configured, details



def resolve_runtime(env: dict[str, str]) -> tuple[str, str, str | None, bool]:
    endpoint = env.get("BRAINK_CHAT_RUNTIME", "").strip() or env.get("EXPO_PUBLIC_API_BASE_URL", "").strip()
    auth_ok, _ = auth_state(env)
    if endpoint and auth_ok:
        return "bridged_runtime", endpoint.rstrip("/"), None, auth_ok
    if endpoint and not auth_ok:
        return "deterministic_local", "", "BRAINK runtime endpoint present without complete EXPO_PUBLIC auth mapping", auth_ok
    return "deterministic_local", "", "BRAINK_CHAT_RUNTIME not configured; using deterministic local runtime", auth_ok



def build_execution_policy() -> dict[str, Any]:
    return {
        "allowed_commands": {name: " ".join(command) for name, command in ALLOWED_COMMANDS.items()},
        "network_policy": "BRAINK runtime only via BRAINK_CHAT_RUNTIME when auth mapping is complete",
        "fallback_policy": "deterministic_local on missing runtime or incomplete auth mapping",
        "audit_trail": "per-step JSON report + raw logs",
    }



def build_plan(intent: str, explicit_route: str | None, env: dict[str, str]) -> RoutePlan:
    routes, reasoning = classify_routes(intent)
    if explicit_route:
        if explicit_route not in ROUTE_ORDER:
            raise ValueError(f"Unsupported explicit route: {explicit_route}")
        ordered = [explicit_route] + [route for route in routes if route != explicit_route]
        routes = []
        for route in ordered:
            if route not in routes:
                routes.append(route)
        reasoning[explicit_route] = "forced by workflow input"

    runtime_mode, endpoint, fallback_reason, auth_ok = resolve_runtime(env)
    return RoutePlan(
        intent=intent,
        routes=routes,
        route_reasoning=reasoning,
        runtime_mode=runtime_mode,
        runtime_endpoint=endpoint,
        fallback_reason=fallback_reason,
        auth_configured=auth_ok,
        knowledge_center_runtime_path=env.get("IL_LLM_RUNTIME_PATH", str(ROOT)),
        execution_policy=build_execution_policy(),
    )



def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (ROOT / "reports").mkdir(parents=True, exist_ok=True)



def prepare_child_env(plan: RoutePlan, base_env: dict[str, str]) -> dict[str, str]:
    env = dict(base_env)
    env.setdefault("IL_LLM_RUNTIME_PATH", str(ROOT))
    if plan.runtime_mode == "bridged_runtime":
        env["BRAINK_CHAT_RUNTIME"] = plan.runtime_endpoint
    else:
        env.pop("BRAINK_CHAT_RUNTIME", None)
    return env



def run_named_command(name: str, output_dir: Path, env: dict[str, str]) -> StepResult:
    command = ALLOWED_COMMANDS[name]
    log_path = output_dir / f"{name}.log"
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.write_text(completed.stdout, encoding="utf-8")
    status = "success" if completed.returncode == 0 else "failure"
    markers: dict[str, Any] = {}
    if name == "runtime_smoke":
        markers = extract_smoke_markers(completed.stdout)
    try:
        display_log_path = str(log_path.relative_to(ROOT))
    except ValueError:
        display_log_path = str(log_path)

    return StepResult(
        name=name,
        command=command,
        returncode=completed.returncode,
        status=status,
        log_path=display_log_path,
        markers=markers,
    )



def extract_smoke_markers(output: str) -> dict[str, Any]:
    markers: dict[str, Any] = {}
    for line in output.splitlines():
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        if key.startswith("SMOKE_"):
            markers[key] = value.strip()
    return markers



def smoke_validation(markers: dict[str, Any]) -> dict[str, Any]:
    status = markers.get("SMOKE_STATUS") == "DONE"
    routes = markers.get("SMOKE_ROUTES", "")
    alignment_text = markers.get("SMOKE_AUDIT_ALIGNMENT", "0")
    try:
        alignment = float(alignment_text)
    except ValueError:
        alignment = 0.0
    return {
        "status_done": status,
        "has_self_sustained_coder": "self_sustained_coder" in routes,
        "has_kex_hyperdrive": "kex_hyperdrive" in routes,
        "alignment": alignment,
    }



def artifact_summary() -> dict[str, bool]:
    paths = {
        "proof_packet": ROOT / "reports/BRAINK_kex_self_sustain_packet.json",
        "ethics_report": ROOT / "reports/kex_ethics_check.json",
        "stack_audit": ROOT / "NativeChatBot/build/braink_stack_alignment_report.json",
        "kex_hyperdrive": ROOT / "NativeChatBot/build/kex_hyperdrive_repo_calibration_report.json",
        "self_sustained_coding": ROOT / "NativeChatBot/build/kex_self_sustained_coding_report.json",
    }
    return {name: path.is_file() for name, path in paths.items()}



def workflow_summary(plan: RoutePlan, steps: list[StepResult], halt_reason: str | None = None) -> dict[str, Any]:
    smoke_step = next((step for step in steps if step.name == "runtime_smoke"), None)
    smoke = smoke_validation(smoke_step.markers if smoke_step else {})
    artifacts = artifact_summary()
    success = all(step.returncode == 0 for step in steps)
    success = success and smoke["status_done"] and smoke["has_self_sustained_coder"] and smoke["has_kex_hyperdrive"]
    success = success and abs(smoke["alignment"] - 1.0) < ALIGNMENT_TOLERANCE
    success = success and all(artifacts.values())
    return {
        "success": success,
        "runtime_mode": plan.runtime_mode,
        "fallback_used": plan.runtime_mode == "deterministic_local",
        "fallback_reason": plan.fallback_reason,
        "halt_reason": halt_reason,
        "alignment": smoke["alignment"],
        "proof_packet_verified": any(step.name == "self_sustain_verify" and step.returncode == 0 for step in steps),
        "routes": plan.routes,
        "artifacts": artifacts,
    }



def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")



def command_plan(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    ensure_output_dir(output_dir)
    plan = build_plan(args.intent, args.route, dict(os.environ))
    payload = asdict(plan)
    write_json(output_dir / "orchestration_plan.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0



def command_run(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    ensure_output_dir(output_dir)
    plan = build_plan(args.intent, args.route, dict(os.environ))
    child_env = prepare_child_env(plan, dict(os.environ))

    steps: list[StepResult] = []
    halt_reason: str | None = None
    for name in ALLOWED_COMMANDS:
        step = run_named_command(name, output_dir, child_env)
        steps.append(step)
        if step.returncode != 0:
            halt_reason = f"Stopped after {name} failed with exit code {step.returncode}."
            break

    report = {
        "plan": asdict(plan),
        "steps": [asdict(step) for step in steps],
        "summary": workflow_summary(plan, steps, halt_reason=halt_reason),
    }
    write_json(output_dir / "workflow_report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["summary"]["success"] else 1



def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "artifacts/braink-workflow"),
        help="Directory for plan/report artifacts.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BRAINK-native workflow orchestrator for GitHub Actions.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    plan = subcommands.add_parser("plan", help="Emit the BRAINK route and execution plan.")
    add_common_args(plan)
    plan.add_argument("--intent", default=DEFAULT_INTENT, help="BRAINK objective text for route classification.")
    plan.add_argument("--route", choices=ROUTE_ORDER, help="Optional explicit primary route.")
    plan.set_defaults(func=command_plan)

    run = subcommands.add_parser("run", help="Execute the BRAINK route plan locally for CI.")
    add_common_args(run)
    run.add_argument("--intent", default=DEFAULT_INTENT, help="BRAINK objective text for route classification.")
    run.add_argument("--route", choices=ROUTE_ORDER, help="Optional explicit primary route.")
    run.set_defaults(func=command_run)
    return parser



def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
