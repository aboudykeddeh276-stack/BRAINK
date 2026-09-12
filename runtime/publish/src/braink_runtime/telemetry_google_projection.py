from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .google_adapter import build_services


@dataclass(frozen=True)
class SheetProjectionConfig:
    spreadsheet_id: str
    telemetry_range: str = "TCP_SOCKET_TELEMETRY!B11:N17"
    reconciliation_range: str = "TELEMETRY_RECONCILIATION!A:N"


def _stream_rows(snapshot: dict[str, Any]) -> list[list[Any]]:
    if snapshot.get("claim_class") != "POOL_SHARE_TELEMETRY":
        raise ValueError("UNSUPPORTED_TELEMETRY_CLAIM_CLASS")
    if snapshot.get("bitcoin_block_discovery") is not False:
        raise ValueError("POOL_TELEMETRY_CANNOT_PROMOTE_BLOCK_DISCOVERY")
    rows=[]
    for i, stream in enumerate(snapshot.get("streams", []), start=1):
        rows.append([
            i,
            stream["worker_id"],
            stream.get("route_proof", ""),
            stream.get("extranonce1", ""),
            stream.get("job_id", ""),
            stream.get("difficulty") or "",
            stream.get("status", "ONLINE"),
            stream.get("last_seen", "BRAINK_READBACK"),
            stream["accepted_shares"],
            stream["rejected_shares"],
            stream["reject_rate_pct"] / 100.0,
            stream.get("last_reject_reason", "NONE"),
            "ACTIVE • BRAINK_READBACK",
        ])
    return rows


def project_snapshot(
    snapshot: dict[str, Any],
    *,
    credentials_file: str,
    token_file: str,
    config: SheetProjectionConfig,
) -> dict[str, Any]:
    """Project canonical BRAINK telemetry into Sheets.

    Sheets is readback/projection only. No socket, pool or transport authority is
    inferred from a successful spreadsheet write.
    """
    rows=_stream_rows(snapshot)
    services=build_services(credentials_file, token_file)
    sheets=services["sheets"]
    body={"values": rows}
    result=(
        sheets.spreadsheets().values()
        .update(
            spreadsheetId=config.spreadsheet_id,
            range=config.telemetry_range,
            valueInputOption="RAW",
            body=body,
        )
        .execute()
    )
    return {
        "status":"PROJECTED",
        "spreadsheet_id":config.spreadsheet_id,
        "updated_range":result.get("updatedRange"),
        "updated_rows":result.get("updatedRows", len(rows)),
        "claim_class":"POOL_SHARE_TELEMETRY",
        "transport_authority":"carrier/host runtime",
        "sheet_role":"PROJECTION_READBACK_ONLY",
    }


def reconcile_rows(registry_rows: list[list[Any]], telemetry_rows: list[list[Any]]) -> dict[str, Any]:
    """Compare worker accepted/rejected counts across two workbook projections.

    Expected row shape for both inputs is:
    worker_id, blade_name, ..., accepted_shares, rejected_shares
    where accepted/rejected are the last four-ish fields depending on caller.
    This function accepts normalized dictionaries more conveniently through
    reconcile_records; it is retained for simple row adapters.
    """
    return reconcile_records(_normalize_records(registry_rows), _normalize_records(telemetry_rows))


def _num(value: Any) -> int:
    if isinstance(value, str):
        value=value.replace(",", "").strip()
    return int(value)


def _normalize_records(rows: list[list[Any]]) -> list[dict[str, Any]]:
    out=[]
    for row in rows:
        if not row or len(row) < 11:
            continue
        worker=str(row[1]).strip() if str(row[0]).strip().isdigit() else str(row[0]).strip()
        if not worker.startswith("keddeh.blade"):
            continue
        # CONNECTED_NODE_REGISTRY uses accepted/rejected at indexes 8/9 when
        # worker id is index 0. TCP_SOCKET_TELEMETRY uses indexes 9/10 with a
        # leading blank column in raw sheet form. Callers should normalize away
        # that blank. We locate the two share fields from the tail for stability.
        accepted=_num(row[-4])
        rejected=_num(row[-3])
        out.append({"worker_id":worker,"accepted_shares":accepted,"rejected_shares":rejected})
    return out


def reconcile_records(registry: list[dict[str, Any]], telemetry: list[dict[str, Any]]) -> dict[str, Any]:
    reg={r["worker_id"]:r for r in registry}
    tel={r["worker_id"]:r for r in telemetry}
    workers=sorted(set(reg)|set(tel))
    drift=[]
    for worker in workers:
        a=reg.get(worker); b=tel.get(worker)
        if a is None or b is None:
            drift.append({"worker_id":worker,"field":"ROW","registry":a,"telemetry":b,"status":"MISSING_PROJECTION"})
            continue
        for field in ("accepted_shares","rejected_shares"):
            if _num(a[field]) != _num(b[field]):
                drift.append({
                    "worker_id":worker,
                    "field":field.upper(),
                    "registry":_num(a[field]),
                    "telemetry":_num(b[field]),
                    "status":"DRIFT",
                })
    return {
        "status":"PASS" if not drift else "DRIFT_DETECTED",
        "workers_compared":len(workers),
        "drift_count":len(drift),
        "drift":drift,
        "promotion_rule":"No telemetry projection is canonical until cross-projection drift is zero.",
    }
