from pathlib import Path
import tempfile, unittest
from runtime.braink_core import BrainkRoot, MachineIdentity, ObjectEnvelope, BlockFileController, Replicator, Reconciler, ServiceFabric, ServiceDescriptor, IntegrityError, AuthorityError, ReadOnlyBoundaryPort

class CoreContracts(unittest.TestCase):
    def test_vfs_is_resolver_only(self):
        root=BrainkRoot(MachineIdentity('M1','B1','L1'),'DEVICE://M1/STORAGE/BLOCK0','KEX_STORAGE_CONTROLLER://M1','KEX://MACHINE/M1/STORAGE/','KEX://VFS/M1/','RESOLVER_ONLY','LEX://BRAINK/M1','VEC://M1/LOCAL','OBS://M1','PROOF://M1')
        root.validate()
        bad=BrainkRoot(**{**root.__dict__,'vfs_role':'STORAGE_MEDIUM'})
        with self.assertRaises(IntegrityError): bad.validate()

    def test_controller_persists_canonical_object(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'machine.vdisk'
            with BlockFileController(p,create=True) as c:
                digest=c.write_object(256,{'braink_id':'B1','vfs_role':'RESOLVER_ONLY'}); c.sync()
            with BlockFileController(p) as c: got=c.read_object(256)
            self.assertEqual(got['sha256'],digest); self.assertEqual(got['value']['braink_id'],'B1')

    def test_replication_preserves_payload_not_lineage(self):
        src=ObjectEnvelope.create(object_id='O1',object_type='CLOUD',lexical_id='LEX://O1',lineage_id='L1',revision=7,payload={'x':1})
        dst=Replicator.replicate(src,'L2')
        self.assertEqual(src.payload_sha256,dst.payload_sha256); self.assertNotEqual(src.lineage_id,dst.lineage_id)

    def test_reconciliation_preserves_local_lineage(self):
        local=ObjectEnvelope.create(object_id='O1',object_type='CLOUD',lexical_id='LEX://O1',lineage_id='L1',revision=1,payload={'x':1})
        remote=ObjectEnvelope.create(object_id='O1',object_type='CLOUD',lexical_id='LEX://O1',lineage_id='L2',revision=2,payload={'x':2})
        out=Reconciler.reconcile(local,remote)
        self.assertEqual(out.lineage_id,'L1'); self.assertEqual(out.revision,2); self.assertEqual(out.payload,{'x':2})

    def test_semantic_resolution_is_unique(self):
        f=ServiceFabric(MachineIdentity('M1','B1','L1'),{'DOMAIN_ROOT':ServiceDescriptor('DOMAIN_ROOT','LEX://DOMAIN/keddeh.com','VEC://M1/DOMAIN','KEX://M1/DOMAIN','DOMAIN_ADAPTER','INTERNAL')})
        self.assertEqual(f.resolve('LEX://DOMAIN/keddeh.com').object_type,'DOMAIN_ROOT')

    def test_observation_never_implies_mutation(self):
        p=ReadOnlyBoundaryPort('PUBLIC_DNS',lambda t:{'state':'OBSERVED','target':t})
        self.assertEqual(p.observe('keddeh.com')['state'],'OBSERVED')
        with self.assertRaises(AuthorityError): p.mutate('keddeh.com',{'set':'A'})

if __name__=='__main__': unittest.main()
