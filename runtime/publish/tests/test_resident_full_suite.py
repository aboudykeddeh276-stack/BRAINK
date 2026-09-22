import tempfile
from braink_runtime.full_suite_kernel import ResidentBRAINKAdapters
from braink_runtime.layer2_reconciler import ObservedManifestation

class ResidentActuator:
    def __init__(self, fail_once=False):
        self.fail_once=fail_once
        self.failed=False
        self.seen={}
    def execute(self, action, key):
        if key in self.seen:
            return self.seen[key]
        if self.fail_once and not self.failed:
            self.failed=True
            raise RuntimeError("resident injected actuator fault")
        obs=ObservedManifestation(action.manifestation_id,action.endpoint,action.generation,"ATTACHED")
        self.seen[key]=obs
        return obs

def test_resident_stack_tot_directory_l2_layer19_journal():
    with tempfile.TemporaryDirectory() as td:
        a=ResidentBRAINKAdapters(("A","B","C"),f"{td}/evidence.jsonl",ResidentActuator())
        result=a.kernel().execute(
            run_id="run:resident:1",coordinate="X2/Y2",generation=1,actor_id="A",
            authority_ref="authority://resident",payload=b"BRAINK-R2",media_type="application/octet-stream",
            operation="MATERIALISE",target="runtime://resident",route_id="route://resident"
        )
        assert result.state=="COMMITTED"
        assert a.directory.records["X2/Y2"].generation==1
        assert len(a.journal.recover())==1
        assert a.tot.receipts[-1].committed_root==result.consensus_root

def test_resident_stack_l2_failure_prevents_layer_seal_and_evidence():
    with tempfile.TemporaryDirectory() as td:
        a=ResidentBRAINKAdapters(("A","B","C"),f"{td}/evidence.jsonl",ResidentActuator(fail_once=True))
        try:
            a.kernel().execute(
                run_id="run:resident:2",coordinate="X2/Y2",generation=1,actor_id="A",
                authority_ref="authority://resident",payload=b"BRAINK-R2",media_type="application/octet-stream",
                operation="MATERIALISE",target="runtime://resident",route_id="route://resident"
            )
            assert False, "expected failure"
        except Exception as exc:
            assert "L2_NOT_CONVERGED" in str(exc)
        assert len(a.journal.recover())==0
