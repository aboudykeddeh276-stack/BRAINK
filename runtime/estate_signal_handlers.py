from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

BASE = Path(__file__).resolve().parents[1]
WBOS = BASE / "modules" / "kex_wbos"
if str(WBOS) not in sys.path:
    sys.path.insert(0, str(WBOS))

from action_runtime import execute_action, read_workbook_table  # type: ignore
from runtime.runtime_registry import RuntimeRegistry


def _record(state: Dict[str, Any], *, operation: str, target: str, result: Dict[str, Any]) -> Dict[str, Any]:
    history = list(state.get("signal_history", []))
    history.append({"operation": operation, "target": target, "result": result})
    state["signal_history"] = history[-128:]
    state["last_operation"] = operation
    state["last_target"] = target
    state["last_result"] = result
    return state


def kex_action_handler(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    request = payload.get("request")
    if not isinstance(request, dict):
        raise ValueError("KEX_ACTION requires payload.request object")
    result = execute_action(request)
    return _record(state, operation="KEX_ACTION", target=str(request.get("target", "")), result=result)


def casepath_dispatch_handler(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    request = payload.get("request")
    if not isinstance(request, dict):
        raise ValueError("CASEPATH_DISPATCH requires payload.request object")
    normalized = {
        "authority": request.get("authority"),
        "actionType": "CASEPATH_DISPATCH",
        "target": request.get("activeTarget") or request.get("target"),
        "payload": {
            "packetId": request.get("packetId"),
            "processId": request.get("processId"),
            "actionQueue": request.get("actionQueue", []),
            "proofTarget": request.get("proofTarget"),
        },
    }
    result = execute_action(normalized)
    return _record(state, operation="CASEPATH_DISPATCH", target=str(normalized.get("target", "")), result=result)


def workbook_read_handler(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    workbook_id = str(payload.get("workbook_id", ""))
    table_id = str(payload.get("table_id", ""))
    if not workbook_id or not table_id:
        raise ValueError("WORKBOOK_READ requires workbook_id and table_id")
    code, result = read_workbook_table(workbook_id, table_id)
    result = {"http_status": code, **result}
    return _record(state, operation="WORKBOOK_READ", target=f"{workbook_id}:{table_id}", result=result)


def runtime_register_handler(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    spec = payload.get("runtime")
    if not isinstance(spec, dict):
        raise ValueError("RUNTIME_REGISTER requires payload.runtime object")
    registry_path = Path(payload.get("registry_path") or (BASE / "runtime" / "state" / "runtime_registry.sqlite"))
    row = RuntimeRegistry(registry_path).upsert(spec)
    return _record(state, operation="RUNTIME_REGISTER", target=str(spec.get("runtime_id", "")), result=row)


def runtime_desired_state_handler(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    runtime_id = str(payload.get("runtime_id", ""))
    desired_state = str(payload.get("desired_state", ""))
    if not runtime_id or not desired_state:
        raise ValueError("RUNTIME_DESIRED_STATE requires runtime_id and desired_state")
    registry_path = Path(payload.get("registry_path") or (BASE / "runtime" / "state" / "runtime_registry.sqlite"))
    row = RuntimeRegistry(registry_path).set_desired(runtime_id, desired_state)
    return _record(state, operation="RUNTIME_DESIRED_STATE", target=runtime_id, result=row)


def register_estate_handlers(runtime: Any) -> None:
    runtime.register("KEX_ACTION", kex_action_handler)
    runtime.register("CASEPATH_DISPATCH", casepath_dispatch_handler)
    runtime.register("WORKBOOK_READ", workbook_read_handler)
    runtime.register("RUNTIME_REGISTER", runtime_register_handler)
    runtime.register("RUNTIME_DESIRED_STATE", runtime_desired_state_handler)
