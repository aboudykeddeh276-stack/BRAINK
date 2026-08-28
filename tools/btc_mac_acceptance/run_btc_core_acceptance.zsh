#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ROOT="$ROOT/runs/$RUN_ID"
CORE_ROOT="$RUN_ROOT/bitcoin-core"
DATADIR="$RUN_ROOT/bitcoin-data"
BRAINK_ROOT="$RUN_ROOT/BRAINK"
EVIDENCE="$RUN_ROOT/evidence"
mkdir -p "$CORE_ROOT" "$DATADIR" "$EVIDENCE"

exec > >(tee -a "$EVIDENCE/EXECUTION.log") 2>&1

fail() {
  local reason="$1"
  printf '{"status":"FAIL","reason":%s,"run_id":%s}\n' \
    "$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$reason")" \
    "$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$RUN_ID")" \
    > "$EVIDENCE/FINAL_STATUS.json"
  echo "FAIL: $reason"
  exit 1
}

command -v curl >/dev/null || fail "curl missing"
command -v python3 >/dev/null || fail "python3 missing"
command -v shasum >/dev/null || fail "shasum missing"
command -v unzip >/dev/null || fail "unzip missing"

ARCH="$(uname -m)"
case "$ARCH" in
  arm64) CORE_ARCHIVE="bitcoin-31.1-arm64-apple-darwin.tar.gz" ;;
  x86_64) CORE_ARCHIVE="bitcoin-31.1-x86_64-apple-darwin.tar.gz" ;;
  *) fail "unsupported macOS architecture: $ARCH" ;;
esac

CORE_BASE="https://bitcoincore.org/bin/bitcoin-core-31.1"
cd "$CORE_ROOT"
curl --fail --location --retry 4 --retry-delay 2 --output SHA256SUMS "$CORE_BASE/SHA256SUMS"
curl --fail --location --retry 4 --retry-delay 2 --output "$CORE_ARCHIVE" "$CORE_BASE/$CORE_ARCHIVE"
EXPECTED="$(awk -v f="$CORE_ARCHIVE" '$2==f {print $1}' SHA256SUMS)"
[[ -n "$EXPECTED" ]] || fail "archive hash absent from official SHA256SUMS"
ACTUAL="$(shasum -a 256 "$CORE_ARCHIVE" | awk '{print $1}')"
[[ "$EXPECTED" == "$ACTUAL" ]] || fail "Bitcoin Core archive SHA-256 mismatch"
printf '{"source":"bitcoincore.org","version":"31.1","archive":"%s","architecture":"%s","sha256":"%s","verified":true}\n' "$CORE_ARCHIVE" "$ARCH" "$ACTUAL" > "$EVIDENCE/BITCOIN_CORE_BINARY_PROVENANCE.json"

tar -xzf "$CORE_ARCHIVE"
BITCOIND="$(find "$CORE_ROOT" -type f -path '*/bin/bitcoind' -perm -111 | head -1)"
BITCOIN_CLI="$(find "$CORE_ROOT" -type f -path '*/bin/bitcoin-cli' -perm -111 | head -1)"
[[ -x "$BITCOIND" ]] || fail "bitcoind not found after verified extraction"
[[ -x "$BITCOIN_CLI" ]] || fail "bitcoin-cli not found after verified extraction"

BRAINK_COMMIT="5304e4ef35a72356f730abde354e53d2a4f3d8d7"
BRAINK_ARCHIVE="$RUN_ROOT/BRAINK-$BRAINK_COMMIT.zip"
curl --fail --location --retry 4 --retry-delay 2 \
  --output "$BRAINK_ARCHIVE" \
  "https://github.com/aboudykeddeh276-stack/BRAINK/archive/$BRAINK_COMMIT.zip"
unzip -q "$BRAINK_ARCHIVE" -d "$RUN_ROOT"
EXTRACTED_BRAINK="$RUN_ROOT/BRAINK-$BRAINK_COMMIT"
[[ -d "$EXTRACTED_BRAINK/runtime" ]] || fail "BRAINK source archive did not extract as expected"
mv "$EXTRACTED_BRAINK" "$BRAINK_ROOT"

python3 - "$BRAINK_ROOT" "$EVIDENCE/BRAINK_SOURCE_PROVENANCE.json" "$BRAINK_COMMIT" <<'PY'
import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); out=pathlib.Path(sys.argv[2]); commit=sys.argv[3]
files={
 "runtime/btc_consensus.py":"a37058aad5efd44a8361c9148fa7360ac7176373",
 "runtime/btc_miner_runtime.py":"1d60586ccb7bdcfef4859db5a988237f2cee3b1e",
 "runtime/btc_workload_substrate.py":"93ddb2a7d3e26c8575326569094e4f11823f7e3d",
}
rows=[]
for path,expected_blob in files.items():
    data=(root/path).read_bytes()
    actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
    if actual != expected_blob:
        raise SystemExit(f"Git blob mismatch for {path}: {actual} != {expected_blob}")
    rows.append({"path":path,"git_blob_sha1":actual,"sha256":hashlib.sha256(data).hexdigest()})
out.write_text(json.dumps({"verified":True,"commit":commit,"files":rows},indent=2)+"\n")
PY

"$BITCOIND" -regtest=1 -server=1 -daemon=1 -datadir="$DATADIR" -listen=0 -fallbackfee=0.00001
CORE_STARTED=1
cleanup() {
  if [[ "${CORE_STARTED:-0}" == "1" ]]; then
    "$BITCOIN_CLI" -regtest -datadir="$DATADIR" stop >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

READY=0
for i in {1..90}; do
  if "$BITCOIN_CLI" -regtest -datadir="$DATADIR" getblockchaininfo > "$EVIDENCE/GETBLOCKCHAININFO_INITIAL.json" 2> "$EVIDENCE/BITCOIN_CORE_STARTUP_ERROR.txt"; then
    READY=1; break
  fi
  sleep 1
done
[[ "$READY" == "1" ]] || fail "Bitcoin Core regtest RPC did not become ready"

"$BITCOIN_CLI" -regtest -datadir="$DATADIR" getnetworkinfo > "$EVIDENCE/GETNETWORKINFO.json"
"$BITCOIN_CLI" -regtest -datadir="$DATADIR" createwallet braink-regtest-miner > "$EVIDENCE/CREATEWALLET.json"
PAYOUT="$($BITCOIN_CLI -regtest -datadir="$DATADIR" -rpcwallet=braink-regtest-miner getnewaddress '' bech32)"
[[ "$PAYOUT" == bcrt1* ]] || fail "regtest payout address is not bcrt bech32"
printf '%s\n' "$PAYOUT" > "$EVIDENCE/REGTEST_PAYOUT_ADDRESS.txt"

export BTC_NETWORK=regtest
export BTC_DATADIR="$DATADIR"
export BTC_RPC_URL="http://127.0.0.1:18443"
export BTC_PAYOUT_ADDRESS="$PAYOUT"
export BTC_MIN_VERIFICATION_PROGRESS="0.0"
export KEX_ALLOW_LIVE_SUBMIT="1"
export KEX_MAX_HASHES_PER_JOB="1000000"
export KEX_EXTRANONCE="0"
export KEX_BTC_STATE_DIR="$RUN_ROOT/braink-state"
export BTC_RPC_TIMEOUT="10"
export BTC_TEMPLATE_TIMEOUT="30"
export BTC_SUBMIT_TIMEOUT="30"

python3 - "$BRAINK_ROOT" "$EVIDENCE/GETBLOCKTEMPLATE_PREEXECUTION.json" <<'PY'
import json,sys
sys.path.insert(0,str(__import__('pathlib').Path(sys.argv[1])/'runtime'))
from btc_workload_substrate import request_template
ok,t=request_template()
if not ok: raise SystemExit(json.dumps(t))
__import__('pathlib').Path(sys.argv[2]).write_text(json.dumps(t,indent=2,sort_keys=True)+"\n")
PY

set +e
python3 "$BRAINK_ROOT/runtime/btc_miner_runtime.py" > "$EVIDENCE/BRAINK_MINER_RESULT.json" 2> "$EVIDENCE/BRAINK_MINER_STDERR.txt"
MINER_RC=$?
set -e
[[ "$MINER_RC" == "0" ]] || fail "BRAINK BTC miner process exited non-zero: $MINER_RC"

python3 - "$EVIDENCE/BRAINK_MINER_RESULT.json" <<'PY'
import json,sys
r=json.load(open(sys.argv[1]))
assert r.get('state')=='ACCEPTED_BY_NODE', r
assert (r.get('submission') or {}).get('accepted') is True, r
assert (r.get('submission') or {}).get('rpc_result') is None, r
print('BRAINK candidate accepted by Bitcoin Core')
PY

"$BITCOIN_CLI" -regtest -datadir="$DATADIR" getblockchaininfo > "$EVIDENCE/GETBLOCKCHAININFO_AFTER_SUBMISSION.json"
COUNT="$($BITCOIN_CLI -regtest -datadir="$DATADIR" getblockcount)"
BEST="$($BITCOIN_CLI -regtest -datadir="$DATADIR" getbestblockhash)"
[[ "$COUNT" -ge 1 ]] || fail "Core blockcount did not advance after accepted submitblock"
"$BITCOIN_CLI" -regtest -datadir="$DATADIR" getblock "$BEST" 2 > "$EVIDENCE/ACCEPTED_BLOCK_READBACK.json"

MATURE_ADDR="$($BITCOIN_CLI -regtest -datadir="$DATADIR" -rpcwallet=braink-regtest-miner getnewaddress '' bech32)"
"$BITCOIN_CLI" -regtest -datadir="$DATADIR" generatetoaddress 100 "$MATURE_ADDR" > "$EVIDENCE/MATURITY_CONFIRMATION_BLOCKS.json"
"$BITCOIN_CLI" -regtest -datadir="$DATADIR" getblock "$BEST" 2 > "$EVIDENCE/ACCEPTED_BLOCK_AFTER_100_CONFIRMATIONS.json"
"$BITCOIN_CLI" -regtest -datadir="$DATADIR" -rpcwallet=braink-regtest-miner listunspent 1 9999999 > "$EVIDENCE/WALLET_LISTUNSPENT.json"

python3 - "$EVIDENCE" "$RUN_ID" "$COUNT" "$BEST" <<'PY'
import hashlib,json,pathlib,sys
p=pathlib.Path(sys.argv[1]); run_id=sys.argv[2]; count=int(sys.argv[3]); best=sys.argv[4]
miner=json.loads((p/'BRAINK_MINER_RESULT.json').read_text())
block=json.loads((p/'ACCEPTED_BLOCK_AFTER_100_CONFIRMATIONS.json').read_text())
receipt={
 'schema':'keddeh.systems.btc.core.target.acceptance.v1',
 'run_id':run_id,
 'network':'regtest',
 'bitcoin_core_version':'31.1',
 'corrected_block_bound_workload_executed':True,
 'submitblock_accepted':miner.get('state')=='ACCEPTED_BY_NODE' and miner.get('submission',{}).get('accepted') is True,
 'accepted_block_hash':best,
 'blockcount_immediately_after_submission':count,
 'accepted_block_confirmations_after_maturity_run':block.get('confirmations'),
 'coinbase_maturity_threshold_exercised':(block.get('confirmations') or 0) >= 101,
 'hashes_tested':miner.get('hashes_tested'),
 'candidate':miner.get('candidate'),
 'claim_boundary':'Real Bitcoin Core regtest acceptance and maturity proof. Not mainnet reward, ASIC throughput, pool share acceptance, energy efficiency, or realised fiat/BTC profit.'
}
(p/'BITCOIN_CORE_ACCEPTANCE_AND_MATURITY_RECEIPT.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
rows=[]
for f in sorted(p.iterdir()):
 if f.is_file(): rows.append({'file':f.name,'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
(p/'EVIDENCE_SHA256.json').write_text(json.dumps({'files':rows},indent=2)+'\n')
assert receipt['submitblock_accepted']
assert receipt['coinbase_maturity_threshold_exercised']
PY

cp "$EVIDENCE/BITCOIN_CORE_ACCEPTANCE_AND_MATURITY_RECEIPT.json" "$ROOT/evidence/LATEST_BITCOIN_CORE_ACCEPTANCE_AND_MATURITY_RECEIPT.json"
cp "$EVIDENCE/EVIDENCE_SHA256.json" "$ROOT/evidence/LATEST_EVIDENCE_SHA256.json"
printf '{"status":"PASS","run_id":"%s","run_root":"%s","bitcoin_core_acceptance":true,"coinbase_maturity":true}\n' "$RUN_ID" "$RUN_ROOT" > "$EVIDENCE/FINAL_STATUS.json"
cp "$EVIDENCE/FINAL_STATUS.json" "$ROOT/evidence/LATEST_FINAL_STATUS.json"

echo "PASS: corrected BTC workload accepted by real Bitcoin Core regtest; 100 confirmation extension completed."
echo "Evidence: $EVIDENCE"
