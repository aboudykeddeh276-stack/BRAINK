import json, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from tot_safety_kernel import *
from kex_coordinate_directory import CoordinateDirectory
from layer2_reconciler import Layer2Reconciler

Q1=("TRIAD_ALPHA:A","TRIAD_ALPHA:B","TRIAD_BETA:A","TRIAD_BETA:B")
Q2=("TRIAD_ALPHA:B","TRIAD_ALPHA:C","TRIAD_GAMMA:A","TRIAD_GAMMA:B")

class TestToTSafety(unittest.TestCase):
    def make(self):
        td=tempfile.TemporaryDirectory(); p=Path(td.name)/"kernel.json"; k=ToTSafetyKernel(p); self.addCleanup(td.cleanup); return k,p
    def elect(self,k,term=1,candidate="TRIAD_ALPHA:A",q=Q1): return k.elect(term=term,candidate=candidate,voters=q)
    def test_01_topology_nine_stable_virtual_voters(self): self.assertEqual(len(VOTERS),9)
    def test_02_local_quorum(self): self.assertTrue(is_local_quorum(["TRIAD_ALPHA:A","TRIAD_ALPHA:B"],"TRIAD_ALPHA"))
    def test_03_global_quorum(self): self.assertTrue(is_global_quorum(Q1))
    def test_04_single_triad_not_global(self): self.assertFalse(is_global_quorum(("TRIAD_ALPHA:A","TRIAD_ALPHA:B","TRIAD_ALPHA:C")))
    def test_05_quorum_intersection_theorem_shape(self): self.assertEqual(quorum_intersection_minimum()["shared_voters"],1)
    def test_06_election_requires_global_quorum(self):
        k,_=self.make()
        with self.assertRaises(SafetyViolation): k.elect(term=1,candidate="TRIAD_ALPHA:A",voters=("TRIAD_ALPHA:A","TRIAD_ALPHA:B"))
    def test_07_term_monotonic(self):
        k,_=self.make(); self.elect(k)
        with self.assertRaises(SafetyViolation): k.elect(term=1,candidate="TRIAD_BETA:A",voters=Q1)
    def test_08_append_commit(self):
        k,_=self.make(); self.elect(k); o=k.transition("X",{"n":1},Q1); self.assertEqual(o["commit_index"],1)
    def test_09_stale_term_fenced(self):
        k,_=self.make(); self.elect(k); p=k.propose("X",{"n":1}); k.elect(term=2,candidate="TRIAD_BETA:A",voters=Q1)
        with self.assertRaises(SafetyViolation): k.approve(p,"TRIAD_ALPHA:A")
    def test_10_conflicting_vote_same_term_index_rejected(self):
        k,_=self.make(); self.elect(k); p1=k.propose("X",{"n":1}); p2=Proposal.create(term=1,index=1,leader=k.leader,previous_root=k.committed_root,operation="X",payload={"n":2}); k.approve(p1,"TRIAD_ALPHA:A")
        with self.assertRaises(SafetyViolation): k.approve(p2,"TRIAD_ALPHA:A")
    def test_11_commit_requires_approved_certificate(self):
        k,_=self.make(); self.elect(k); p=k.propose("X",{"n":1})
        with self.assertRaises(SafetyViolation): k.commit(p,Q1)
    def test_12_conflicting_second_proposal_cannot_rewrite_committed_index(self):
        k,_=self.make(); self.elect(k); k.transition("X",{"n":1},Q1); p=Proposal.create(term=1,index=1,leader=k.leader,previous_root=GENESIS_ROOT,operation="X",payload={"n":2})
        with self.assertRaises(SafetyViolation): k.commit(p,Q2)
    def test_13_restart_replays_verified_head(self):
        k,p=self.make(); self.elect(k); k.transition("X",{"n":1},Q1); root=k.committed_root; k2=ToTSafetyKernel(p); self.assertEqual(k2.committed_root,root); self.assertEqual(k2.verify_log()["state"],"LOG_VERIFIED")
    def test_14_state_tamper_rejected(self):
        k,p=self.make(); self.elect(k); data=json.loads(p.read_text()); data["commit_index"]=99; p.write_text(json.dumps(data))
        with self.assertRaises(SafetyViolation): ToTSafetyKernel(p)
    def test_15_partition_without_global_quorum_cannot_commit(self):
        k,_=self.make(); self.elect(k); p=k.propose("X",{"n":1}); q=("TRIAD_ALPHA:A","TRIAD_ALPHA:B","TRIAD_BETA:A")
        for v in q: k.approve(p,v)
        with self.assertRaises(SafetyViolation): k.commit(p,q)

class TestDirectory(unittest.TestCase):
    def make(self):
        td=tempfile.TemporaryDirectory(); root=Path(td.name); k=ToTSafetyKernel(root/"kernel.json"); k.elect(term=1,candidate="TRIAD_ALPHA:A",voters=Q1); d=CoordinateDirectory(kernel=k,state_path=root/"directory.json"); self.addCleanup(td.cleanup); return k,d,root
    def test_16_define_requires_commit(self):
        k,d,_=self.make(); out=d.define("KEX://SERVICE/A",kind="SERVICE"); self.assertEqual(out["state"],"COORDINATE_DEFINED_COMMITTED"); self.assertEqual(d.resolve("KEX://SERVICE/A")["commit_index"],1)
    def test_17_duplicate_coordinate_rejected(self):
        k,d,_=self.make(); d.define("KEX://SERVICE/A",kind="SERVICE")
        with self.assertRaises(ValueError): d.define("KEX://SERVICE/A",kind="SERVICE")
    def test_18_desired_state_is_authority_commit(self):
        k,d,_=self.make(); d.define("KEX://SERVICE/A",kind="SERVICE"); root=k.committed_root; d.set_desired("KEX://SERVICE/A",{"replicas":3}); self.assertNotEqual(k.committed_root,root); self.assertEqual(d.resolve("KEX://SERVICE/A")["record"]["desired"]["replicas"],3)
    def test_19_observation_does_not_change_accepted_state(self):
        k,d,_=self.make(); d.define("KEX://SERVICE/A",kind="SERVICE"); root=k.committed_root; d.observe_manifestation("KEX://SERVICE/A",{"state":"UNREACHABLE"}); self.assertEqual(k.committed_root,root)
    def test_20_zero_observations_does_not_delete_coordinate(self):
        k,d,_=self.make(); d.define("KEX://SERVICE/A",kind="SERVICE"); r=d.resolve("KEX://SERVICE/A"); self.assertEqual(r["state"],"RESOLVED_ACCEPTED_COORDINATE"); self.assertEqual(r["manifestation_observations"],[])
    def test_21_directory_replay_from_committed_log(self):
        k,d,root=self.make(); d.define("KEX://SERVICE/A",kind="SERVICE",desired={"x":1}); d2=CoordinateDirectory(kernel=ToTSafetyKernel(root/"kernel.json"),state_path=root/"directory2.json"); self.assertEqual(d2.resolve("KEX://SERVICE/A")["record"]["desired"],{"x":1})

class TestReconciler(unittest.TestCase):
    def make(self):
        td=tempfile.TemporaryDirectory(); root=Path(td.name); k=ToTSafetyKernel(root/"kernel.json"); k.elect(term=1,candidate="TRIAD_ALPHA:A",voters=Q1); d=CoordinateDirectory(kernel=k,state_path=root/"directory.json"); d.define("KEX://SERVICE/A",kind="SERVICE",desired={"replicas":3,"route":"x"}); r=Layer2Reconciler(d); self.addCleanup(td.cleanup); return k,d,r
    def test_22_plan_diff(self):
        k,d,r=self.make(); p=r.plan("KEX://SERVICE/A",{"replicas":1,"route":"x"}); self.assertEqual(len(p.actions),1); self.assertEqual(p.actions[0]["field"],"replicas")
    def test_23_noop_when_converged(self):
        k,d,r=self.make(); p=r.plan("KEX://SERVICE/A",{"replicas":3,"route":"x"}); out=r.apply(p,lambda a:a); self.assertEqual(out["state"],"NOOP_ALREADY_CONVERGED")
    def test_24_stale_plan_fenced_after_authority_change(self):
        k,d,r=self.make(); p=r.plan("KEX://SERVICE/A",{}); d.set_desired("KEX://SERVICE/A",{"replicas":2})
        with self.assertRaises(RuntimeError): r.apply(p,lambda a:a)
    def test_25_apply_actions_do_not_mutate_accepted_state(self):
        k,d,r=self.make(); p=r.plan("KEX://SERVICE/A",{}); root=k.committed_root; out=r.apply(p,lambda a:{"done":a["field"]}); self.assertEqual(out["state"],"PLAN_APPLIED_MANIFESTATION_ACTIONS_ONLY"); self.assertEqual(k.committed_root,root)
    def test_26_managed_extra_field_detaches(self):
        k,d,r=self.make(); p=r.plan("KEX://SERVICE/A",{"replicas":3,"route":"x","managed_old":"y"}); self.assertEqual(p.actions[0]["action"],"DETACH_UNDESIRED_MANAGED_FIELD")

if __name__=='__main__': unittest.main(verbosity=2)

class TestExhaustiveTopology(unittest.TestCase):
    def test_27_all_global_quorums_intersect(self):
        from itertools import combinations
        qs=[]
        for r in range(1,len(VOTERS)+1):
            for comb in combinations(VOTERS,r):
                if is_global_quorum(comb): qs.append(set(comb))
        self.assertTrue(qs)
        self.assertEqual(min(len(a & b) for i,a in enumerate(qs) for b in qs[i+1:]),1)
    def test_28_any_three_crash_failures_leave_some_global_quorum(self):
        from itertools import combinations
        voters=set(VOTERS)
        for failed in combinations(VOTERS,3):
            self.assertTrue(is_global_quorum(voters-set(failed)), failed)
    def test_29_four_crashes_can_block_progress(self):
        failed={"TRIAD_ALPHA:A","TRIAD_ALPHA:B","TRIAD_BETA:A","TRIAD_BETA:B"}
        self.assertFalse(is_global_quorum(set(VOTERS)-failed))

class TestIndependentReplicaHarness(unittest.TestCase):
    def make(self):
        import tempfile
        from tot_replica_harness import ReplicaHarness
        td=tempfile.TemporaryDirectory(); h=ReplicaHarness(Path(td.name)); self.addCleanup(td.cleanup); return h
    def test_30_nine_independent_journals_exist(self):
        h=self.make(); self.assertEqual(len(list((h.root/'voters').glob('*.json'))),9)
    def test_31_replicated_commit_only_reaches_certificate_voters(self):
        h=self.make(); h.election(term=1,candidate='TRIAD_ALPHA:A',reachable=Q1); h.transition('X',{'n':1},reachable=Q1); heads=h.heads(); self.assertEqual(heads['TRIAD_ALPHA:A']['index'],1); self.assertEqual(heads['TRIAD_GAMMA:A']['index'],0)
    def test_32_stale_candidate_cannot_win_next_term(self):
        h=self.make(); h.election(term=1,candidate='TRIAD_ALPHA:A',reachable=Q1); h.transition('X',{'n':1},reachable=Q1)
        with self.assertRaises(SafetyViolation): h.election(term=2,candidate='TRIAD_GAMMA:A',reachable=('TRIAD_ALPHA:A','TRIAD_ALPHA:B','TRIAD_GAMMA:A','TRIAD_GAMMA:B'))
    def test_33_up_to_date_candidate_can_win_with_other_group(self):
        h=self.make(); h.election(term=1,candidate='TRIAD_ALPHA:A',reachable=Q1); h.transition('X',{'n':1},reachable=Q1); out=h.election(term=2,candidate='TRIAD_ALPHA:A',reachable=('TRIAD_ALPHA:A','TRIAD_ALPHA:B','TRIAD_GAMMA:A','TRIAD_GAMMA:B')); self.assertEqual(out['state'],'REPLICA_LEADER_ELECTED')
    def test_34_catchup_rehydrates_stale_virtual_voter(self):
        h=self.make(); h.election(term=1,candidate='TRIAD_ALPHA:A',reachable=Q1); h.transition('X',{'n':1},reachable=Q1); self.assertEqual(h.heads()['TRIAD_GAMMA:A']['index'],0); h.catch_up('TRIAD_GAMMA:A'); self.assertEqual(h.heads()['TRIAD_GAMMA:A']['index'],1)
    def test_35_single_triad_partition_cannot_commit(self):
        h=self.make(); h.election(term=1,candidate='TRIAD_ALPHA:A',reachable=Q1)
        with self.assertRaises(SafetyViolation): h.transition('X',{'n':1},reachable=('TRIAD_ALPHA:A','TRIAD_ALPHA:B','TRIAD_ALPHA:C'))
    def test_36_replica_journal_tamper_detected(self):
        from tot_replica_harness import Replica
        h=self.make(); p=h.replicas['TRIAD_ALPHA:A'].path; d=json.loads(p.read_text()); d['commit_index']=99; p.write_text(json.dumps(d))
        with self.assertRaises(SafetyViolation): Replica('TRIAD_ALPHA:A',p)