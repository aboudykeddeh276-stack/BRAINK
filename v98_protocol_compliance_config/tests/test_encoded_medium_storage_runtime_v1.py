import sys, unittest, tempfile
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
        self.assertEqual(o.address,m.geometry_address(2,3,"L1"))

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
        self.assertEqual(v.read("/braink")["payload"],'{"braink":"B1","state":"resident"}')

    def test_legacy_reparenting(self):
        expected={
            "volume_registry":"OBSERVATION_PROOF_REGISTRY",
            "sheet_rows":"PROJECTION_READBACK",
            "100TB_rows":"ADDRESS_LAW_PROJECTION",
            "IP_endpoint":"CARRIER_PROJECTION"
        }
        for k,v in expected.items(): self.assertEqual(reconcile_legacy_claim(k)["authoritative"],v)

    def test_activation_writes_receipt_and_outbox(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            receipt=activate(root)
            self.assertEqual(receipt["status"],"VERIFIED")
            self.assertTrue((root/"evidence/encoded_medium_reconciliation_receipt.json").exists())
            self.assertTrue((root/"runtime_volume/encoded_medium/current.json").exists())
            self.assertTrue((root/"runtime_volume/outbox/encoded_medium_reconciliation/authoritative.handoff.json").exists())

if __name__=="__main__": unittest.main(verbosity=2)
