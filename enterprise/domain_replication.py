REQUIRED_RECEIPTS=("REGISTRAR","DNS","INGRESS","TLS","HTTP_READBACK")

def qualify(receipts):
    passed={k for k,v in receipts.items() if v=="PASS"}
    missing=[r for r in REQUIRED_RECEIPTS if r not in passed]
    return {
        "state":"PUBLIC_LIVE" if not missing else "STAGED_NOT_PUBLIC_LIVE",
        "missing":missing,
    }

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
 "patch_id":"CP-TC-20260727-C01",
 "target":"/your-data.html",
 "release_id":"CP-V50-CASEPATH-DIRECT-RUNTIME-20260828",
 "actuator_state":"IDENTIFIED",
 "external_mutation_state":"REQUIRES_BOUND_PRODUCTION_ORIGIN"
}
