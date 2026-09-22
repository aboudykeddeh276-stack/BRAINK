import copy
import pytest

from braink_runtime.layer1_9_reconciler import Layer1to9Reconciler, LayerViolation, LayerReceipt, digest
from braink_runtime.full_suite_kernel import FullSuiteKernel

def payloads(tag="A"):
    return {
        1: {"payload_hash": "a"*64, "payload_bytes": 10, "media_type": "application/octet-stream"},
        2: {"actor_id": "node:A", "authority_ref": "authority://test", "capability": "EXECUTE"},
        3: {"coordinate": "X2/Y2", "directory_root": digest({"d": tag}), "coordinate_generation": 1},
        4: {"mapping": "logical-coordinate", "origin": "Singularity:1", "geometry_root": digest({"g": tag})},
        5: {"route_id": "route:test", "signal_type": "EXECUTE", "destination": "runtime://test"},
        6: {"epoch": 1, "index": 1, "commit_root": digest({"c": tag}), "quorum_size": 2, "membership_hash": digest({"m": tag}), "certificate_hash": digest({"qc": tag}), "receipt_hash": digest({"receipt": tag})},
        7: {"operation": "EXECUTE", "target": "runtime://test", "result_root": digest({"r": tag})},
        8: {"observer_id": "observer://test", "before_root": digest({"x": 1}), "after_root": digest({"x": 2}), "changed": True},
        9: {"evidence_root": digest({"e": tag}), "receipt_count": 8, "claim_state": "OBSERVED"},
    }

def test_all_nine_layers_commit_and_verify():
    r=Layer1to9Reconciler()
    receipts=r.reconcile_all(run_id="run:1",generation=1,payloads=payloads())
    assert len(receipts)==9
    assert r.verify_chain()==r.root
    assert r.receipt_root==receipts[-1].receipt_hash

def test_same_generation_same_payload_is_idempotent():
    r=Layer1to9Reconciler()
    first=r.reconcile_all(run_id="run:1",generation=1,payloads=payloads())
    second=r.reconcile_all(run_id="run:1",generation=1,payloads=payloads())
    assert first==second

def test_same_generation_payload_conflict_rejected():
    r=Layer1to9Reconciler()
    r.reconcile_all(run_id="run:1",generation=1,payloads=payloads())
    changed=payloads("B")
    changed[3]["coordinate"]="X3/Y2"
    with pytest.raises(LayerViolation,match="SAME_GENERATION_PAYLOAD_CONFLICT"):
        r.reconcile_all(run_id="run:1",generation=1,payloads=changed)

def test_missing_layer_contract_rejected():
    p=payloads(); del p[7]
    with pytest.raises(LayerViolation,match="ALL_NINE_LAYERS_REQUIRED"):
        Layer1to9Reconciler().reconcile_all(run_id="run:1",generation=1,payloads=p)

def test_zero_identity_and_coordinate_rejected():
    p=payloads(); p[2]["actor_id"]="0"
    with pytest.raises(LayerViolation,match="IDENTITY_ZERO_ACTOR_REJECTED"):
        Layer1to9Reconciler().reconcile_all(run_id="run:1",generation=1,payloads=p)
    p=payloads(); p[3]["coordinate"]="0"
    with pytest.raises(LayerViolation,match="COORDINATE_ZERO_REJECTED"):
        Layer1to9Reconciler().reconcile_all(run_id="run:2",generation=1,payloads=p)

def test_observation_lie_rejected():
    p=payloads(); p[8]["changed"]=False
    with pytest.raises(LayerViolation,match="OBSERVATION_CHANGE_FLAG_MISMATCH"):
        Layer1to9Reconciler().reconcile_all(run_id="run:1",generation=1,payloads=p)

def test_layer9_cannot_seal_with_wrong_receipt_count():
    p=payloads(); p[9]["receipt_count"]=7
    with pytest.raises(LayerViolation,match="EVIDENCE_RECEIPT_COUNT_MUST_BE_EIGHT_PRIOR_LAYERS"):
        Layer1to9Reconciler().reconcile_all(run_id="run:1",generation=1,payloads=p)

def test_fault_aborts_suffix_and_retry_same_generation_converges():
    r=Layer1to9Reconciler()
    with pytest.raises(LayerViolation,match="LAYER_7_EXECUTION_FAILED"):
        r.reconcile_all(run_id="run:1",generation=1,payloads=payloads(),fault_layer=7)
    assert set(r.state)==set(range(1,7))
    assert r.failures[-1].layer==7
    receipts=r.reconcile_all(run_id="run:1",generation=1,payloads=payloads())
    assert len(receipts)==9 and r.verify_chain()==r.root

def test_new_upstream_generation_invalidates_old_suffix():
    r=Layer1to9Reconciler()
    r.reconcile_all(run_id="run:1",generation=1,payloads=payloads())
    p=payloads("B")
    p[3]["coordinate_generation"]=2
    r.apply(run_id="run:1",layer=1,generation=2,payload=p[1])
    assert set(r.state)=={1}
    with pytest.raises(LayerViolation,match="PIPELINE_NOT_SEALED"):
        _=r.root

def test_receipt_tamper_detected():
    r=Layer1to9Reconciler()
    r.reconcile_all(run_id="run:1",generation=1,payloads=payloads())
    bad=copy.deepcopy(r._committed[5])
    object.__setattr__(bad,"receipt_hash","0"*64)
    r._committed[5]=bad
    with pytest.raises(LayerViolation,match="LAYER_5_RECEIPT_HASH_MISMATCH"):
        r.verify_chain()

class FakeAdapters:
    def __init__(self, corrupt_consensus=False, fail_evidence=False):
        self.index=0
        self.directory={}
        self.targets={"runtime://test":{"state":"IDLE"}}
        self.corrupt_consensus=corrupt_consensus
        self.fail_evidence=fail_evidence
        self.seen={}
    def consensus(self, actor, command, payload):
        self.index += 1
        root=digest({"i":self.index,"actor":actor,"command":command,"payload":payload})
        out={"epoch":1,"index":self.index,"commit_root":root,"quorum_size":2,"membership_hash":digest({"members":["A","B","C"]}),"certificate_hash":digest({"qc":self.index}),"receipt_hash":digest({"receipt":self.index})}
        if self.corrupt_consensus: del out["commit_root"]
        return out
    def directory_apply(self, coordinate, generation, payload):
        self.directory[coordinate]={"generation":generation,"payload":dict(payload)}
        return {"directory_root":digest(self.directory),"coordinate_generation":generation}
    def execute(self, operation, payload, key):
        if key in self.seen: return self.seen[key]
        self.targets["runtime://test"]={"state":"APPLIED","payload":dict(payload),"key":key}
        out={"result_root":digest(self.targets["runtime://test"])}
        self.seen[key]=out
        return out
    def observe(self,target):
        return dict(self.targets[target])
    def evidence(self,kind,bundle):
        if self.fail_evidence: return ""
        return digest({"kind":kind,"bundle":bundle})

def make_kernel(f):
    return FullSuiteKernel(
        consensus_commit=f.consensus,
        directory_apply=f.directory_apply,
        execution_apply=f.execute,
        observer_read=f.observe,
        evidence_append=f.evidence,
    )

def test_full_kernel_executes_and_seals():
    f=FakeAdapters()
    result=make_kernel(f).execute(
        run_id="run:kernel:1",coordinate="X2/Y2",generation=1,actor_id="node:A",
        authority_ref="authority://test",payload=b"BRAINK",media_type="application/octet-stream",
        operation="EXECUTE",target="runtime://test",route_id="route:test"
    )
    assert result.state=="COMMITTED"
    assert len(result.layer9_root)==64 and len(result.evidence_root)==64

def test_full_kernel_missing_consensus_readback_fails_closed():
    f=FakeAdapters(corrupt_consensus=True)
    with pytest.raises(LayerViolation,match="CONSENSUS_ADAPTER_MISSING:commit_root"):
        make_kernel(f).execute(
            run_id="run:kernel:2",coordinate="X2/Y2",generation=1,actor_id="node:A",
            authority_ref="authority://test",payload=b"BRAINK",media_type="application/octet-stream",
            operation="EXECUTE",target="runtime://test",route_id="route:test"
        )

def test_full_kernel_evidence_append_failure_not_committed():
    f=FakeAdapters(fail_evidence=True)
    with pytest.raises(LayerViolation,match="EVIDENCE_APPEND_FAILED"):
        make_kernel(f).execute(
            run_id="run:kernel:3",coordinate="X2/Y2",generation=1,actor_id="node:A",
            authority_ref="authority://test",payload=b"BRAINK",media_type="application/octet-stream",
            operation="EXECUTE",target="runtime://test",route_id="route:test"
        )


def test_consensus_certificate_shape_required():
    p=payloads()
    p[6]["certificate_hash"]="not-a-hash"
    with pytest.raises(LayerViolation,match="CONSENSUS_CERTIFICATE_HASH_INVALID"):
        Layer1to9Reconciler().reconcile_all(run_id="run:bad-consensus",generation=1,payloads=p)
