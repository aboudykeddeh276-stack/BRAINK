import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
M=json.loads((ROOT/"docs/estate/R89_ROOT_SURFACE_INDEX_COMPACT_20261123.json").read_text())

class RootMachineCarrierLineageR89(unittest.TestCase):
    def test_canonical_architect_and_architecture(self):
        self.assertEqual(M["architect"],"A. Keddeh")
        self.assertEqual(M["canonicalArchitecture"],"KS-BRAINK-IL-LLM")
    def test_logical_root_is_not_carrier(self):
        r=M["rootMachine"]
        self.assertEqual(r["logicalIdentity"],"volume://keddeh/braink/root")
        self.assertNotEqual(r["logicalIdentity"],r["carrierIdentity"])
        self.assertNotEqual(r["logicalIdentity"],r["projectionIdentity"])
        self.assertNotEqual(r["logicalIdentity"],r["materialisationIdentity"])
        self.assertFalse(r["isOneOf15ResidentHtmlRoots"])
        self.assertFalse(r["currentCarrierByteBindingEstablished"])
    def test_root_v16_is_historical_and_unrecovered(self):
        r=M["historicalRootV16Carrier"]
        self.assertEqual(r["carrierId"],"carrier://html/root-v16")
        self.assertEqual(r["declaredBytes"],3741393)
        self.assertEqual(r["declaredSha256"],"50a894e92fe06be3b19168d741b84bf6f6169fbc7130bbf0c2332649d8371c53")
        self.assertFalse(r["exactSourceRecovered"])
        self.assertEqual(r["classification"],"HISTORICAL_UNBOUND_DOCUMENT_ELEMENT_REFERENCE")
    def test_p11_and_architecture_scripts_are_copied_forward(self):
        e=M["embeddedContracts"]
        self.assertEqual(e["p11CarrierModel"]["bytes"],36154)
        self.assertEqual(e["p11CarrierModel"]["sha256"],"81961d6df7458f46882f676fb5f4d3161847ad2af40d7694b2b7f27f48889fc2")
        self.assertEqual(e["p11CarrierModel"]["identicalAcross"],["v27","v28","r4S29Container"])
        self.assertEqual(e["architectureRoot"]["bytes"],7618)
        self.assertEqual(e["architectureRoot"]["sha256"],"fcae9e23dd75bc203fdebc01c4028808a9b6903ba4b36093d16e0c7c7a5ae44c")
    def test_v28_parent_is_exact_v27(self):
        s=M["sourceFiles"]
        self.assertEqual(M["embeddedContracts"]["v28LineageManifest"]["parentSha256"],s["v27"]["sha256"])
        self.assertTrue(M["embeddedContracts"]["v28LineageManifest"]["parentSha256MatchesV27"])
    def test_r4_is_separate_executable_volume(self):
        r=M["r4ExecutableVolume"]
        self.assertEqual(r["logicalIdentity"],"braink://volume/r4")
        self.assertTrue(r["distinctFromRootMachine"])
        self.assertEqual(r["bytes"],13050075)
        self.assertEqual(r["sha256"],"5e55b7c3179d2afd246929bd5793186af65c8025ca4b65a32a06b10dbfe6c592")
    def test_all_15_resident_roots_match(self):
        c=M["estateCounts"]
        self.assertEqual(c["residentHtmlRoots"],15)
        self.assertEqual(c["residentRootPayloadsPassed"],15)
        self.assertEqual(c["residentRootPayloadsTotal"],15)
        self.assertEqual(c["residentRootBrowserPass"],12)
        self.assertEqual(c["residentRootBrowserPartialOrFail"],3)
        self.assertTrue(M["crossRegister"]["root_map_vs_identity_ledger_equal"])
        self.assertTrue(M["crossRegister"]["root_map_vs_fabric_equal"])
    def test_atlas_and_root_registers_are_not_flattened(self):
        c=M["estateCounts"]
        self.assertEqual(c["atlasRecords"],12)
        self.assertEqual(c["atlasOnlyIdentities"],4)
        self.assertEqual(c["rootOnlyNotInAtlas"],7)
        self.assertEqual(len(M["residentRootIdentities"]),15)
        self.assertEqual(len(M["atlasIdentities"]),12)
    def test_p11_and_r5_counts_remain_separate(self):
        c=M["estateCounts"]
        self.assertEqual(c["p11LogicalObjects"],76)
        self.assertEqual(c["p11RawCarrierRowsDeclared"],98)
        self.assertEqual(c["p11UniqueCarrierIdsDeclared"],95)
        self.assertEqual(c["p11DuplicateRawRowsUnmappedInR80Detail"],3)
        self.assertEqual(c["p11MultiCarrierLogicalObjects"],19)
        self.assertEqual(c["r5P11Overlap"],23)
        self.assertEqual(c["r5OnlyIdentities"],10)
        self.assertEqual(c["p11OnlyIdentities"],53)
        self.assertEqual(c["r5P11Union"],86)
    def test_resolver_graph_is_separate(self):
        c=M["estateCounts"]
        self.assertEqual(c["resolverGraphObjects"],49)
        self.assertEqual(c["resolverGraphAliases"],107)
        self.assertEqual(c["resolverGraphRelations"],20)
    def test_r5_parent_source_and_base_relations(self):
        r=M["r5ParentAndWorkbookReconciliation"]
        self.assertEqual(r["parentIdentity"],"braink://volume/r5/system-orchestrator")
        self.assertEqual(r["parentSource"]["bytes"],13086990)
        self.assertEqual(r["parentSource"]["sha256"],"9eb1eb8cead2b5f4d941dde024b5f7bbad46f1bdc2ff2e948fb190b841f16ede")
        self.assertEqual(r["embeddedManifest"]["relations"],23)
        self.assertEqual(r["canonicalIdentityCount"],33)
    def test_r5_cross_work_child_is_not_parent(self):
        r=M["r5ParentAndWorkbookReconciliation"]
        self.assertEqual(r["crossWorkChild"]["identity"],"braink://volume/r5/system-orchestrator/cross-work-r1")
        self.assertEqual(r["crossWorkChild"]["relations"],32)
        self.assertEqual(r["crossWorkChild"]["parentBinding"]["sha256"],r["parentSource"]["sha256"])
    def test_r5_workbook_identity_substitution_is_preserved(self):
        r=M["r5ParentAndWorkbookReconciliation"]
        self.assertFalse(r["r5_33Sheet"]["matchesCanonical"])
        self.assertEqual(r["r5_33Sheet"]["missing"],["braink://volume/r5/system-orchestrator"])
        self.assertEqual(r["r5_33Sheet"]["extra"],["braink://volume/r5/system-orchestrator/cross-work-r1"])
        self.assertTrue(r["r5_ReconciliationSheet"]["matchesCanonical"])
    def test_r5_standalone_manifest_is_not_parent_embedded_manifest(self):
        r=M["r5ParentAndWorkbookReconciliation"]["standaloneManifest"]
        self.assertFalse(r["exactFileMaterialized"])
        self.assertTrue(r["embeddedParentManifestIsDifferent"])
        self.assertEqual(r["declaredSha256"],"a7b98529f3356b260ed9fa31834598a54fff171d2db069ade88c22931be3effc")
    def test_no_host_or_consciousness_claim(self):
        b=" ".join(M["qualificationBoundaries"]).lower()
        self.assertIn("no external host pid",b)
        self.assertIn("subjective consciousness is not proven or claimed",b)

if __name__=="__main__": unittest.main()
