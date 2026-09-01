EXECUTION_STATES=(
    "PROCESS_DEFINED",
    "PROCESS_BOUND",
    "PROCESS_EXECUTED",
    "PROCESS_SIGNALED",
)

OBSERVATION_CLASSES=(
    "LOCAL_ACTUATOR_RECEIPT",
    "VFS_BEFORE_AFTER_HASH",
    "RELEASE_MARKER",
    "DNS_OBSERVED",
    "TLS_OBSERVED",
    "INGRESS_OBSERVED",
    "HTTP_READBACK",
)

PUBLIC_OBSERVER_CLASSES=("DNS_OBSERVED","TLS_OBSERVED","INGRESS_OBSERVED","HTTP_READBACK")


def classify_process(*, mechanism_defined, target_bound, operation_invoked, signal_emitted):
    if signal_emitted:
        return "PROCESS_SIGNALED"
    if operation_invoked:
        return "PROCESS_EXECUTED"
    if target_bound:
        return "PROCESS_BOUND"
    if mechanism_defined:
        return "PROCESS_DEFINED"
    return "PROCESS_UNDEFINED"


def classify_projection(observations):
    """Classify observer/readback state without changing process execution state."""
    passed={k for k,v in observations.items() if v=="PASS"}
    missing=[r for r in PUBLIC_OBSERVER_CLASSES if r not in passed]
    if "HTTP_READBACK" in passed:
        state="PUBLIC_PROJECTION_OBSERVED"
    elif passed:
        state="PUBLIC_PROJECTION_PARTIALLY_OBSERVED"
    else:
        state="PUBLIC_PROJECTION_UNOBSERVED"
    return {"state":state,"missing_observer_edges":missing,"observed":sorted(passed)}


def reconcile(*, process_state, observations, conflicts=None):
    projection=classify_projection(observations)
    conflicts=list(conflicts or [])
    return {
        "process_state":process_state,
        "projection_observation_state":projection["state"],
        "observer_edges":projection,
        "conflicts":conflicts,
        "promotion_state":"PROMOTED" if process_state in {"PROCESS_EXECUTED","PROCESS_SIGNALED"} and not conflicts else "RECONCILIATION_REQUIRED",
    }


# Compatibility alias retained for callers that previously used qualify().
# It now classifies public projection observation only and MUST NOT be used as
# an execution-permission or process-existence oracle.
def qualify(receipts):
    return classify_projection(receipts)


DOMAIN_BINDINGS={
 "casepath.com.au":"app://casepath",
 "claimpath.com.au":"app://claimpath",
 "claimpath.org":"app://claimpath",
 "braink.com.au":"app://braink/workbook",
 "braink.store":"app://braink/workbook",
 "braink.studio":"app://braink/workbook",
 "keddeh.com":"app://keddeh/root",
 "braink.keddeh.com":"app://braink/workbook",
 "kex.keddeh.com":"app://kex/computer",
 "mining.keddeh.systems":"app://keddeh/mining",
 "keddehsystems.com":"app://keddeh/root",
 "keddeh.systems":"app://keddeh/root",
}

CASEPATH_CURRENT_PATCH={
 "process":"CASEPATH_GRAPH_BOUND_YOUR_DATA_AMENDMENT",
 "canonical_service":"app://casepath",
 "coordinate":"KEX://DOMAIN/CASEPATH.COM.AU/YOUR-DATA/TRUST-CENTRE",
 "patch_id":"CP-TC-20260727-C01",
 "target":"/your-data.html",
 "release_id":"CP-V50-CASEPATH-DIRECT-RUNTIME-20260828",
 "production_actuator":"mechanic://keddeh/admin/production-actuator",
 "actuator_state":"IDENTIFIED",
 "process_state":"PROCESS_BOUND",
 "public_readback_role":"OBSERVER_EDGE_NOT_EXECUTION_GATE",
 "next_transition":"PROCESS_EXECUTED_OR_REJECTED",
}
