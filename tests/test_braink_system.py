from pathlib import Path
import tempfile, unittest
from runtime.braink_core import MachineIdentity, ObjectEnvelope
from runtime.braink_system import MachineRuntime, FabricRuntime

class SystemContracts(unittest.TestCase):
    def test_machine_boot_descendant_services_replication_failover_reconcile(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            p1=d/'m1.vdisk'; p2=d/'m2.vdisk'
            i1=MachineIdentity('KEX-MACHINE-001','BRAINK::KEX-MACHINE-001','LINEAGE::M1')
            m1=MachineRuntime.create(p1,i1)
            i2=MachineRuntime.derive_child_identity(i1,1)
            m2=MachineRuntime.create(p2,i2)
            self.assertNotEqual(m1.boot().identity.braink_id,m2.boot().identity.braink_id)
            self.assertEqual(m2.boot().identity.parent_machine,i1.machine_id)

            m1.install_default_services(); m2.install_default_services()
            fabric=FabricRuntime([m1,m2])
            domain_hits=fabric.resolve('LEX://DOMAIN/keddeh.com')
            self.assertEqual(len(domain_hits),2)

            src=ObjectEnvelope.create(object_id='GLOBAL-OBJECT-001',object_type='CLOUD',lexical_id='LEX://CLOUD/OBJECT/GLOBAL-OBJECT-001',lineage_id=i1.lineage_root,revision=1,payload={'value':'R16'})
            m1.write_state(src)
            fabric.replicate_state(m1,[m2])
            self.assertEqual(m1.read_state().payload_sha256,m2.read_state().payload_sha256)
            self.assertNotEqual(m1.read_state().lineage_id,m2.read_state().lineage_id)

            # Loss is represented by resolver membership/health, not by renaming/corrupting the machine's disk.
            degraded=FabricRuntime([m2])
            hit=degraded.resolve('LEX://DOMAIN/keddeh.com')
            self.assertEqual(hit[0][0].machine_id,i2.machine_id)

            newer=ObjectEnvelope.create(object_id='GLOBAL-OBJECT-001',object_type='CLOUD',lexical_id=src.lexical_id,lineage_id=i2.lineage_root,revision=2,payload={'value':'R16-newer'})
            m2.write_state(newer)
            fabric.reconcile_state(m1,m2)
            self.assertEqual(m1.read_state().payload,{'value':'R16-newer'})
            self.assertEqual(m1.read_state().lineage_id,i1.lineage_root)

if __name__=='__main__': unittest.main()
