#!/usr/bin/env python3
from __future__ import annotations
import json, sqlite3, tempfile, unittest
from pathlib import Path

from tot_safety_kernel import VOTERS, SafetyViolation, is_global_quorum
from tot_process_cluster import ProcessCluster, FaultPlan, NoQuorum, IndeterminateCommit, ReplicaStore
from distributed_coordinate_directory import DirectoryCluster, REPLICA_IDS
from layer2_closed_loop import SandboxActuator, ClosedLoopReconciler

Q_ALPHA_BETA=("TRIAD_ALPHA:A","TRIAD_ALPHA:B","TRIAD_BETA:A","TRIAD_BETA:B")
Q_BETA_GAMMA=("TRIAD_BETA:B","TRIAD_BETA:C","TRIAD_GAMMA:A","TRIAD_GAMMA:B")

class ClusterCase(unittest.TestCase):
    def make_cluster(self):
        td=tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        c=ProcessCluster(Path(td.name)/"tot"); self.addCleanup(c.stop)
        return c, Path(td.name)

class TestProcessCluster(ClusterCase):
    def test_01_nine_real_processes_and_full_wal(self):
        c,_=self.make_cluster(); states=c.all_states()
        pids={states[v]["pid"] for v in VOTERS}
        self.assertEqual(len(pids),9)
        for v in VOTERS:
            self.assertEqual(states[v]["sqlite"]["journal_mode"],"WAL")
            self.assertEqual(states[v]["sqlite"]["synchronous"],2)

    def test_02_elect_commit_restart_and_verify(self):
        c,_=self.make_cluster(); c.elect(term=1,candidate="TRIAD_ALPHA:A",reachable=Q_ALPHA_BETA)
        out=c.transition("X",{"n":1},reachable=Q_ALPHA_BETA)
        self.assertTrue(is_global_quorum(out["committed"]))
        root=out["entry"]["entry_root"]
        c.restart_node("TRIAD_ALPHA:A")
        s=c.state("TRIAD_ALPHA:A")
        self.assertEqual(s["commit_index"],1); self.assertEqual(s["committed_root"],root)
        self.assertEqual(c.verify_all()["state"],"ALL_LIVE_REPLICAS_VERIFIED")

    def test_03_stale_candidate_cannot_reform_quorum(self):
        c,_=self.make_cluster(); c.elect(term=1,candidate="TRIAD_ALPHA:A",reachable=Q_ALPHA_BETA)
        c.transition("X",{"n":1},reachable=Q_ALPHA_BETA)
        with self.assertRaises(NoQuorum):
            c.elect(term=2,candidate="TRIAD_GAMMA:A",reachable=("TRIAD_ALPHA:A","TRIAD_ALPHA:B","TRIAD_GAMMA:A","TRIAD_GAMMA:B"))

    def test_04_whole_triad_isolation_still_commits_through_other_two(self):
        c,_=self.make_cluster(); c.elect(term=1,candidate="TRIAD_BETA:A",reachable=Q_BETA_GAMMA)
        blocked={("TRIAD_BETA:A",v,"APPEND") for v in ("TRIAD_ALPHA:A","TRIAD_ALPHA:B","TRIAD_ALPHA:C")}
        f=FaultPlan(blocked=blocked)
        out=c.transition("X",{"partition":"alpha"},reachable=VOTERS,fault=f)
        self.assertTrue(is_global_quorum(out["committed"]))
        self.assertTrue(all(not v.startswith("TRIAD_ALPHA") for v in out["prepared"]))

    def test_05_only_one_triad_cannot_commit(self):
        c,_=self.make_cluster(); c.elect(term=1,candidate="TRIAD_ALPHA:A",reachable=Q_ALPHA_BETA)
        with self.assertRaises(NoQuorum):
            c.transition("X",{"n":1},reachable=("TRIAD_ALPHA:A","TRIAD_ALPHA:B","TRIAD_ALPHA:C"))

    def test_06_dropped_commit_responses_create_indeterminate_then_recover(self):
        c,_=self.make_cluster(); c.elect(term=1,candidate="TRIAD_ALPHA:A",reachable=Q_ALPHA_BETA)
        drops={("TRIAD_ALPHA:A",v,"COMMIT") for v in ("TRIAD_ALPHA:A","TRIAD_ALPHA:B","TRIAD_BETA:A")}
        # Only TRIAD_BETA:B response is observed, so caller cannot prove commit quorum even though servers apply before response drop.
        f=FaultPlan(drop_response=drops)
        try:
            c.transition("X",{"n":"ambiguous"},reachable=Q_ALPHA_BETA,fault=f)
            self.fail("expected IndeterminateCommit")
        except IndeterminateCommit as exc:
            self.assertFalse(is_global_quorum(exc.commit_acks))
            recovered=c.recover_indeterminate(exc.entry)
            self.assertEqual(recovered["state"],"RECOVERED_COMMITTED_ENTRY")
            self.assertTrue(is_global_quorum(recovered["committed"]))

    def test_07_process_loss_and_rejoin_catchup(self):
        c,_=self.make_cluster(); c.elect(term=1,candidate="TRIAD_ALPHA:A",reachable=Q_ALPHA_BETA)
        c.kill_node("TRIAD_GAMMA:A")
        c.transition("X",{"n":1},reachable=Q_ALPHA_BETA)
        c.restart_node("TRIAD_GAMMA:A")
        self.assertEqual(c.state("TRIAD_GAMMA:A")["commit_index"],0)
        c.catch_up("TRIAD_GAMMA:A")
        self.assertEqual(c.state("TRIAD_GAMMA:A")["commit_index"],1)

    def test_08_sqlite_payload_tamper_is_detected(self):
        c,root=self.make_cluster(); c.elect(term=1,candidate="TRIAD_ALPHA:A",reachable=Q_ALPHA_BETA)
        c.transition("X",{"n":1},reachable=Q_ALPHA_BETA)
        victim="TRIAD_ALPHA:A"; c.kill_node(victim)
        db=root/"tot"/"voters"/f"{victim.replace(':','__')}.sqlite3"
        con=sqlite3.connect(db); con.execute("UPDATE log SET payload_json='{}' WHERE idx=1"); con.commit(); con.close()
        with self.assertRaises(SafetyViolation): ReplicaStore(victim,db)

    def test_08b_failed_minority_prepare_is_superseded_only_in_higher_term(self):
        c,_=self.make_cluster(); c.elect(term=1,candidate="TRIAD_ALPHA:A",reachable=Q_ALPHA_BETA)
        with self.assertRaises(NoQuorum):
            c.transition("X",{"n":"minority"},reachable=("TRIAD_ALPHA:A","TRIAD_ALPHA:B"))
        # Same-term conflicting retry stays fenced.
        with self.assertRaises(NoQuorum):
            c.transition("X",{"n":"same-term-conflict"},reachable=Q_ALPHA_BETA)
        # A strictly higher elected term extending the committed head may repair the abandoned prepare.
        c.elect(term=2,candidate="TRIAD_BETA:A",reachable=Q_ALPHA_BETA)
        out=c.transition("X",{"n":"higher-term-recovery"},reachable=Q_ALPHA_BETA)
        self.assertEqual(out["entry"]["index"],1)
        self.assertTrue(is_global_quorum(out["committed"]))

class TestDirectoryAndLayer2(ClusterCase):
    def prepare(self):
        c,root=self.make_cluster(); c.elect(term=1,candidate="TRIAD_ALPHA:A",reachable=Q_ALPHA_BETA)
        c.transition("COORDINATE_DEFINE",{"coordinate":"KEX://SERVICE/A","kind":"SERVICE","desired":{"managed_files":{"service.json":{"replicas":3,"route":"x"}}},"metadata":{}},reachable=Q_ALPHA_BETA)
        d=DirectoryCluster(root/"directory",c); self.addCleanup(d.stop); d.sync()
        return c,d,root

    def test_09_three_directory_processes_converge(self):
        c,d,_=self.prepare(); self.assertEqual(len(set(d.pids.values())),3); self.assertTrue(d.converged())
        states=[d.state(r) for r in REPLICA_IDS]
        self.assertEqual(len({s["directory_root"] for s in states}),1)
        for s in states:
            self.assertEqual(s["sqlite"]["journal_mode"],"WAL"); self.assertEqual(s["sqlite"]["synchronous"],2)

    def test_10_directory_offline_then_catchup_converges(self):
        c,d,_=self.prepare(); d.kill("DIR_GAMMA")
        c.transition("COORDINATE_DESIRED_SET",{"coordinate":"KEX://SERVICE/A","desired":{"managed_files":{"service.json":{"replicas":4,"route":"x"}}}},reachable=Q_ALPHA_BETA)
        d.sync(("DIR_ALPHA","DIR_BETA")); self.assertEqual(d.state("DIR_ALPHA")["applied_commit_index"],2)
        d.restart("DIR_GAMMA"); self.assertEqual(d.state("DIR_GAMMA")["applied_commit_index"],1)
        d.sync(("DIR_GAMMA",)); self.assertTrue(d.converged()); self.assertEqual(d.state("DIR_GAMMA")["applied_commit_index"],2)

    def test_11_closed_loop_actuator_mutates_then_noops(self):
        c,d,root=self.prepare(); act=SandboxActuator(root/"manifestation"); self.addCleanup(act.close)
        r=ClosedLoopReconciler(d,"DIR_ALPHA",act)
        before=d.state("DIR_ALPHA")["directory_root"]
        out=r.reconcile_until_converged("KEX://SERVICE/A")
        self.assertEqual(out["state"],"CLOSED_LOOP_CONVERGED")
        target=root/"manifestation"/"service.json"; self.assertTrue(target.exists())
        self.assertEqual(json.loads(target.read_text()),{"replicas":3,"route":"x"})
        self.assertEqual(d.state("DIR_ALPHA")["directory_root"],before)
        self.assertEqual(out["passes"][-1]["apply"]["state"],"NOOP_ALREADY_CONVERGED")
        self.assertEqual(act.sqlite_mode()["synchronous"],2)

    def test_12_external_drift_is_repaired(self):
        c,d,root=self.prepare(); act=SandboxActuator(root/"manifestation"); self.addCleanup(act.close); r=ClosedLoopReconciler(d,"DIR_ALPHA",act)
        r.reconcile_until_converged("KEX://SERVICE/A")
        (root/"manifestation"/"service.json").write_text('{"replicas":99}')
        p=r.plan("KEX://SERVICE/A"); self.assertEqual(p.actions[0]["action"],"REPLACE")
        r.apply(p); self.assertEqual(json.loads((root/"manifestation"/"service.json").read_text()),{"replicas":3,"route":"x"})

    def test_13_stale_reconcile_plan_is_fenced(self):
        c,d,root=self.prepare(); act=SandboxActuator(root/"manifestation"); self.addCleanup(act.close); r=ClosedLoopReconciler(d,"DIR_ALPHA",act)
        p=r.plan("KEX://SERVICE/A")
        c.transition("COORDINATE_DESIRED_SET",{"coordinate":"KEX://SERVICE/A","desired":{"managed_files":{"service.json":{"replicas":5,"route":"y"}}}},reachable=Q_ALPHA_BETA)
        d.sync(("DIR_ALPHA",))
        with self.assertRaises(RuntimeError): r.apply(p)

    def test_14_actuator_idempotency_receipt_prevents_duplicate_effect(self):
        c,d,root=self.prepare(); act=SandboxActuator(root/"manifestation"); self.addCleanup(act.close)
        action={"action":"MATERIALISE","path":"x.txt","content":"abc"}; key="K1"
        a=act.apply(action,idempotency_key=key); b=act.apply(action,idempotency_key=key)
        self.assertFalse(a.get("idempotent_replay",False)); self.assertTrue(b["idempotent_replay"])
        count=act.conn.execute("SELECT COUNT(*) FROM receipts WHERE idempotency_key='K1'").fetchone()[0]; self.assertEqual(count,1)

    def test_15_actuator_rejects_escape_path(self):
        c,d,root=self.prepare(); act=SandboxActuator(root/"manifestation"); self.addCleanup(act.close)
        with self.assertRaises(ValueError): act.apply({"action":"MATERIALISE","path":"../escape.txt","content":"x"},idempotency_key="bad")

if __name__ == '__main__': unittest.main(verbosity=2)