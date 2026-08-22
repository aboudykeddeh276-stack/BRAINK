#!/usr/bin/env bash
# R16 independent-observer trigger: semantics unchanged; this mutation exists to execute the installed workflow on a subsequent push.
# R16 execution trigger 2: branch-state refresh after workflow installation.
set -u
DOMAIN="${1:-keddeh.com}"
OUT="${2:-/mnt/data/BRAINK_R15_EXTERNAL_PATH_RECEIPT.json}"
probe() {
  local name="$1"; shift
  local tmp
  tmp=$(mktemp)
  if "$@" >"$tmp" 2>&1; then
    python - "$name" "$tmp" <<'PY'
import json,sys,pathlib
name=sys.argv[1]; p=pathlib.Path(sys.argv[2])
print(json.dumps({"probe":name,"status":"PASS","output":p.read_text(errors="replace")[:4000]}))
PY
  else
    rc=$?
    python - "$name" "$tmp" "$rc" <<'PY'
import json,sys,pathlib
name=sys.argv[1]; p=pathlib.Path(sys.argv[2]); rc=int(sys.argv[3])
text=p.read_text(errors="replace")
cls="DNS_EGRESS_BLOCKED" if "Could not resolve host" in text else "EXECUTION_FAILURE"
print(json.dumps({"probe":name,"status":"FAIL","exit_code":rc,"classification":cls,"output":text[:4000]}))
PY
  fi
  rm -f "$tmp"
}
{
  echo '{"schema":"braink.external-path.r15","domain":"'"$DOMAIN"'","probes":['
  first=1
  for spec in dns_a dns_ns rdap https; do
    [ $first -eq 1 ] || echo ','
    first=0
    case "$spec" in
      dns_a) probe DNS_A curl -fsS --max-time 10 -H 'Accept: application/dns-json' "https://dns.google/resolve?name=$DOMAIN&type=A" ;;
      dns_ns) probe DNS_NS curl -fsS --max-time 10 -H 'Accept: application/dns-json' "https://dns.google/resolve?name=$DOMAIN&type=NS" ;;
      rdap) probe RDAP curl -fsS --max-time 10 "https://rdap.verisign.com/com/v1/domain/$DOMAIN" ;;
      https) probe HTTPS curl -fsS -I --max-time 10 "https://$DOMAIN" ;;
    esac
  done
  echo '],"promotion_rule":"PUBLIC_STATE_ONLY_IF_DIRECT_DOMAIN_READBACK_PASSES"}'
} > "$OUT.tmp"
python - "$OUT.tmp" "$OUT" <<'PY'
import json,sys,pathlib
src=pathlib.Path(sys.argv[1]).read_text()
obj=json.loads(src)
passes=[p for p in obj['probes'] if p['status']=='PASS']
blocked=all(p.get('classification')=='DNS_EGRESS_BLOCKED' for p in obj['probes'])
obj['direct_public_readback']='PASS' if passes else 'NO_DIRECT_READBACK'
obj['execution_path']='DNS_EGRESS_BLOCKED' if blocked else 'PARTIAL_OR_OTHER_FAILURE'
obj['domain_public_state']='OBSERVED' if passes else 'UNKNOWN_FROM_THIS_EXECUTION_LANE'
obj['status']='PASS_BOUNDARY_CLASSIFIED' if not passes and blocked else ('PASS_PUBLIC_OBSERVED' if passes else 'FAIL_UNCLASSIFIED')
pathlib.Path(sys.argv[2]).write_text(json.dumps(obj,indent=2))
print(json.dumps(obj,indent=2))
PY
rm -f "$OUT.tmp"