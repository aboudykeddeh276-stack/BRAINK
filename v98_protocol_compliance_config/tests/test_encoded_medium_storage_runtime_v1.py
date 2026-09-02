import sys, unittest, tempfile, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from keddeh_encoded_medium_storage_runtime_v1 import *

class MediumTests(unittest.TestCase):
    def test_line_is_provenance_not_address(self):
        m=EncodedMedium(8,8)
        a=m.geometry_address(1,1,"L")
        b=m.geometry_address(1,2,"L")
        self.assertNotEqual(a,b)
        self.assertEqual(reconcile_legacy_claim("L#")["authoritative"],"SOURCE_PROVENANCE")

    def test_vfs_is_interpreter_not_medium(self):
        m=EncodedMedium(8,8); c=KEXStorageController(m); v=VFSProjection(c)
        self.assertIs(v.controller.medium,m)
        self.assertNotIsInstance(v,EncodedMedium)
        self.assertEqual(reconcile_legacy_claim("VFS")["authoritative"],"FILESYSTEM_RESOLVER_UTILITY")

    def test_controller_write_read(self):
        m=EncodedMedium(8,8); c=KEXStorageController(m)
        o=c.allocate(2,3,"obj","FILE","L1",b"hello")
        r=c.decode("obj")
        self.assertTrue(r["verified"]); self.assertEqual(r["payload"],"hello")
        self.assertEqual(o.coordinate,(2,3))
        self.assertEqual(o.address,m.geometry_address(2,3,"L1"))

    def test_controller_allocates_next_free_coordinate(self):
        m=EncodedMedium(4,4); c=KEXStorageController(m)
        m.program_cell(1,1,1,"seed")
        c.allocate(1,2,"A","FILE","L-A",b"a")
        o=c.allocate_next("B","FILE","L-B",b"b")
        self.assertEqual(o.coordinate,(1,3))
        self.assertEqual(m.object_coordinates[(1,3)],"B")

    def test_coordinate_reuse_rejected(self):
        m=EncodedMedium(4,4); c=KEXStorageController(m)
        c.allocate(2,2,"A","FILE","L-A",b"a")
        with self.assertRaises(ValueError): c.allocate(2,2,"B","FILE","L-B",b"b")
        with self.assertRaises(ValueError): m.program_cell(2,2,1,"seed")

    def test_zero_rejected_as_weighted_cell(self):
        m=EncodedMedium(4,4)
        with self.assertRaises(ValueError): m.program_cell(1,1,0,"L19")

    def test_same_source_line_can_program_distinct_medium_locations(self):
        m=EncodedMedium(4,4)
        a=m.program_cell(1,1,1,"L19")
        b=m.program_cell(1,2,2,"L19")
        self.assertNotEqual(a,b)
        self.assertEqual(m.cells[(1,1)].provenance,m.cells[(1,2)].provenance)

    def test_braink_boots_from_encoded_root(self):
        ident=MachineIdentity("M1","B1","LINEAGE-1")
        m=EncodedMedium(16,16); c=KEXStorageController(m); v=VFSProjection(c)
        c.allocate(1,1,"BRAINK-GENESIS","BRAINK_ROOT","LINEAGE-1",b'{"braink":"B1","state":"resident"}')
        machine=BRAINKMachine(ident,m,c,v)
        receipt=machine.boot("BRAINK-GENESIS")
        self.assertTrue(receipt["root_verified"])
        self.assertEqual(receipt["root_coordinate"],(1,1))
        self.assertEqual(v.read("/braink")["payload"],'{"braink":"B1","state":"resident"}')

    def test_recursive_constructor_a_b_c_auto_allocates(self):
        m=EncodedMedium(16,16); c=KEXStorageController(m); va=VFSProjection(c)
        m.program_cell(1,1,1,"seed")
        a_id=MachineIdentity("A","BRAINK-A","LINEAGE-A")
        c.allocate(2,1,"ROOT-A","BRAINK_ROOT",a_id.lineage,b'{"braink":"A"}')
        a=BRAINKMachine(a_id,m,c,va); a.boot("ROOT-A")
        b,b_receipt=a.instantiate_child_auto(MachineIdentity("B","BRAINK-B","LINEAGE-B"),"ROOT-B")
        c_machine,c_receipt=b.instantiate_child_auto(MachineIdentity("C","BRAINK-C","LINEAGE-C"),"ROOT-C")
        self.assertEqual(b_receipt["allocation_mode"],"KEX_CONTROLLER_NEXT_FREE")
        self.assertEqual(c_receipt["allocation_mode"],"KEX_CONTROLLER_NEXT_FREE")
        self.assertNotEqual(tuple(b_receipt["child_root_coordinate"]),tuple(c_receipt["child_root_coordinate"]))
        self.assertTrue(b_receipt["medium_inherited_by_reference"]); self.assertTrue(c_receipt["medium_inherited_by_reference"])
        self.assertTrue(b_receipt["child_constructor_bearing"]); self.assertTrue(c_receipt["child_constructor_bearing"])
        self.assertIs(a.medium,b.medium); self.assertIs(b.medium,c_machine.medium)
        self.assertIs(a.controller,b.controller); self.assertIs(b.controller,c_machine.controller)
        self.assertIsNot(a.vfs,b.vfs); self.assertIsNot(b.vfs,c_machine.vfs)
        self.assertEqual(b.parent_machine_id,"A"); self.assertEqual(c_machine.parent_machine_id,"B")
        self.assertTrue(c_machine.boot_receipt["root_verified"])
        self.assertEqual(c_machine.vfs.read("/braink")["metadata"]["lineage"],"LINEAGE-C")

    def test_constructor_requires_booted_parent(self):
        m=EncodedMedium(8,8); c=KEXStorageController(m)
        a=BRAINKMachine(MachineIdentity("A","BA","LA"),m,c,VFSProjection(c))
        with self.assertRaises(RuntimeError): a.instantiate_child_auto(MachineIdentity("B","BB","LB"),"ROOT-B")

    def test_duplicate_object_identity_preserves_existing_state(self):
        m=EncodedMedium(8,8); c=KEXStorageController(m)
        c.allocate(1,1,"OBJ","FILE","L",b"one")
        with self.assertRaises(ValueError): c.allocate(1,2,"OBJ","FILE","L",b"two")
        self.assertEqual(c.decode("OBJ")["payload"],"one")

    def test_legacy_reparenting(self):
        expected={"volume_registry":"OBSERVATION_PROOF_REGISTRY","sheet_rows":"PROJECTION_READBACK","100TB_rows":"ADDRESS_LAW_PROJECTION","IP_endpoint":"CARRIER_PROJECTION"}
        for k,v in expected.items(): self.assertEqual(reconcile_legacy_claim(k)["authoritative"],v)

    def test_activation_writes_recursive_receipt_and_continuation_handoff(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); receipt=activate(root)
            self.assertEqual(receipt["status"],"VERIFIED")
            recursion=receipt["recursive_instantiation"]
            self.assertEqual(recursion["path"],["MACHINE-KEX-20260822","MACHINE-KEX-B","MACHINE-KEX-C"])
            self.assertTrue(recursion["same_medium"]); self.assertTrue(recursion["same_controller"]); self.assertTrue(recursion["independent_vfs"])
            self.assertTrue(recursion["C_root_verified"]); self.assertTrue(recursion["C_constructor_bearing"])
            self.assertEqual(len({tuple(x) for x in recursion["automatic_coordinates"]}),2)
            self.assertEqual(len(recursion["proof"]),64)
            outbox=root/"runtime_volume/outbox/encoded_medium_reconciliation/authoritative.handoff.json"
            payload=json.loads(outbox.read_text())
            self.assertEqual(payload["recursive_proof"],recursion["proof"])
            self.assertEqual(payload["current_machine_id"],"MACHINE-KEX-C")
            self.assertEqual(payload["next_operation"],"instantiate_child_auto")

if __name__=="__main__": unittest.main(verbosity=2)
