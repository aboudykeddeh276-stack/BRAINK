#!/usr/bin/env python3
from __future__ import annotations
import json, tempfile, unittest
from dataclasses import replace
from pathlib import Path

from resident_il_llm import ResidentILLMAdapter, KEXSemanticTranslator, HTMLConceptProjector, SemanticResolutionError
from semantic_boundary_integration import (
    SemanticBoundaryController, ExplicitBinaryBoundary, BinarySubstrateActuator,
    SemanticBoundaryError, bytes_to_bits, encode_ab, pack_ab,
)
from tot_process_cluster import ProcessCluster
from distributed_coordinate_directory import DirectoryCluster

Q=("TRIAD_ALPHA:A","TRIAD_ALPHA:B","TRIAD_BETA:A","TRIAD_BETA:B")
SOURCE=Path(__file__).resolve().parents[1]/"source"/"il_llm_recovered_cells.json"

class TestResidentSemanticBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter=ResidentILLMAdapter(SOURCE)
        cls.translator=KEXSemanticTranslator(cls.adapter)
        cls.controller=SemanticBoundaryController(cls.adapter)

    def test_01_resident_il_llm_is_actual_semantic_source(self):
        s=self.adapter.summary()
        self.assertEqual(s["lexicon_entries"],1084)
        self.assertEqual(s["degraded_lexicon_entries"],2)
        self.assertEqual(s["recovered_router_entries"],71)
        self.assertEqual(s["translator_domains"],7)
        c=self.controller.concept("Information")
        self.assertEqual(c.kex_route,"KEX-L-TRANS")
        self.assertEqual(c.meaning["source_sheet"],"02 - Words (English Lexicon)")
        self.assertEqual(c.meaning["source_row"],13)

    def test_02_semantic_identity_is_symbolic_before_bytes(self):
        c=self.controller.concept("Information")
        html=HTMLConceptProjector.project([c])
        self.assertIn(c.semantic_digest,html)
        self.assertIn(c.coordinate,html)
        self.assertNotIn("KXBD",html)
        self.assertNotIn("KEX_AB",html)
        self.assertNotIn("RAW_BINARY",html)

    def test_03_projection_can_change_without_changing_semantic_digest(self):
        c=self.controller.concept("Information")
        a=HTMLConceptProjector.project([c],title="Projection A")
        b=HTMLConceptProjector.project([c],title="Projection B")
        self.assertNotEqual(a,b)
        self.assertIn(c.semantic_digest,a); self.assertIn(c.semantic_digest,b)

    def test_04_unknown_and_degraded_resident_semantics_fail_closed(self):
        with self.assertRaises(SemanticResolutionError): self.controller.concept("NO_SUCH_RESIDENT_SYMBOL_9A77")
        with self.assertRaises(SemanticResolutionError): self.controller.concept("One")

    def test_05_mutated_meaning_with_stale_digest_is_rejected(self):
        c=self.controller.concept("Information")
        bad=replace(c,meaning={**c.meaning,"dictionary_meaning":"tampered meaning"})
        with self.assertRaises(SemanticBoundaryError): self.controller.validate_concept(bad)

    def test_06_ab_codec_is_canonical_and_adaptive_modes_are_observed(self):
        uniform=b"\x00"*128
        wire,r=ExplicitBinaryBoundary.encode(uniform,"11"*32)
        self.assertEqual(r.encoding,"KEX_AB")
        self.assertTrue(r.roundtrip_equal)
        self.assertEqual(ExplicitBinaryBoundary.decode(wire,expected_semantic_digest="11"*32)[0],uniform)
        alternating=b"\xaa"*128
        wire2,r2=ExplicitBinaryBoundary.encode(alternating,"22"*32)
        self.assertEqual(r2.encoding,"RAW_BINARY")
        self.assertEqual(ExplicitBinaryBoundary.decode(wire2,expected_semantic_digest="22"*32)[0],alternating)
        # Canonical stream: all zeros is segmented into maximal B9 chunks plus remainder.
        toks=encode_ab(bytes_to_bits(b"\x00\x00"))
        self.assertEqual([(t.symbol,t.count) for t in toks],[('B',9),('B',7)])
        self.assertTrue(pack_ab(toks))

    def test_07_binary_tamper_and_semantic_binding_fail_closed(self):
        source=b"symbolic-to-binary boundary"
        wire,_=ExplicitBinaryBoundary.encode(source,"33"*32)
        tampered=bytearray(wire); tampered[-1]^=1
        with self.assertRaises(SemanticBoundaryError): ExplicitBinaryBoundary.decode(bytes(tampered),expected_semantic_digest="33"*32)
        with self.assertRaises(SemanticBoundaryError): ExplicitBinaryBoundary.decode(wire,expected_semantic_digest="44"*32)

class TestCrossLayerClosure(unittest.TestCase):
    def make_stack(self):
        td=tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup); root=Path(td.name)
        adapter=ResidentILLMAdapter(SOURCE); ctl=SemanticBoundaryController(adapter)
        cluster=ProcessCluster(root/"tot"); self.addCleanup(cluster.stop)
        cluster.elect(term=1,candidate="TRIAD_ALPHA:A",reachable=Q)
        return root,ctl,cluster

    def test_08_semantic_digest_survives_tot_directory_and_layer2(self):
        root,ctl,cluster=self.make_stack(); concept=ctl.concept("Information")
        accepted=ctl.define_accepted(cluster,concept,Q,title="Accepted Information")
        dirs=DirectoryCluster(root/"directory",cluster); self.addCleanup(dirs.stop); dirs.sync()
        self.assertTrue(dirs.converged())
        resolved=ctl.verify_accepted(dirs,"DIR_ALPHA",accepted["coordinate"],concept)
        self.assertEqual(resolved["record"]["metadata"]["semantic_digest"],concept.semantic_digest)
        before=resolved["accepted_state_root"]
        out=ctl.reconcile_html(dirs,"DIR_ALPHA",accepted["coordinate"],root/"manifestation")
        self.assertEqual(out["state"],"CLOSED_LOOP_CONVERGED")
        html=(root/"manifestation"/"concept.html").read_text()
        self.assertIn(concept.semantic_digest,html)
        after=dirs.resolve("DIR_ALPHA",accepted["coordinate"])["accepted_state_root"]
        self.assertEqual(before,after)

    def test_09_binary_is_absent_until_explicit_substrate_boundary(self):
        root,ctl,cluster=self.make_stack(); concept=ctl.concept("Mapping")
        accepted=ctl.define_accepted(cluster,concept,Q)
        dirs=DirectoryCluster(root/"directory",cluster); self.addCleanup(dirs.stop); dirs.sync()
        sink=BinarySubstrateActuator(root/"binary")
        symbolic=ctl.materialize_binary(dirs,"DIR_ALPHA",accepted["coordinate"],concept,accepted["html"].encode(),sink,requires_binary=False)
        self.assertEqual(symbolic["state"],"SYMBOLIC_PATH_NO_BINARY_MATERIALIZATION")
        self.assertFalse((root/"binary"/"concept.kxbd").exists())
        binary=ctl.materialize_binary(dirs,"DIR_ALPHA",accepted["coordinate"],concept,accepted["html"].encode(),sink,requires_binary=True)
        self.assertEqual(binary["state"],"BINARY_SUBSTRATE_MATERIALIZED")
        self.assertTrue((root/"binary"/"concept.kxbd").exists())
        self.assertTrue(binary["receipt"]["roundtrip_equal"])
        self.assertEqual(binary["semantic_digest"],concept.semantic_digest)

    def test_10_accepted_semantic_digest_tamper_blocks_binary_lowering(self):
        root,ctl,cluster=self.make_stack(); concept=ctl.concept("Bilateral")
        accepted=ctl.define_accepted(cluster,concept,Q)
        dirs=DirectoryCluster(root/"directory",cluster); self.addCleanup(dirs.stop); dirs.sync()
        cluster.transition("COORDINATE_METADATA_PATCH",{"coordinate":accepted["coordinate"],"patch":{"semantic_digest":"00"*32}},reachable=Q)
        dirs.sync()
        with self.assertRaises(SemanticBoundaryError):
            ctl.materialize_binary(dirs,"DIR_ALPHA",accepted["coordinate"],concept,accepted["html"].encode(),BinarySubstrateActuator(root/"binary"),requires_binary=True)

    def test_11_directory_rejoin_preserves_semantic_authority(self):
        root,ctl,cluster=self.make_stack(); concept=ctl.concept("Language")
        accepted=ctl.define_accepted(cluster,concept,Q)
        dirs=DirectoryCluster(root/"directory",cluster); self.addCleanup(dirs.stop); dirs.sync()
        dirs.kill("DIR_GAMMA")
        cluster.transition("COORDINATE_METADATA_PATCH",{"coordinate":accepted["coordinate"],"patch":{"representation_note":"html-title-independent"}},reachable=Q)
        dirs.sync(("DIR_ALPHA","DIR_BETA"))
        dirs.restart("DIR_GAMMA")
        self.assertLess(dirs.state("DIR_GAMMA")["applied_commit_index"],dirs.state("DIR_ALPHA")["applied_commit_index"])
        dirs.sync(("DIR_GAMMA",))
        self.assertTrue(dirs.converged())
        for r in ("DIR_ALPHA","DIR_BETA","DIR_GAMMA"):
            self.assertEqual(dirs.resolve(r,accepted["coordinate"])["record"]["metadata"]["semantic_digest"],concept.semantic_digest)

    def test_12_html_drift_repair_does_not_redefine_semantics(self):
        root,ctl,cluster=self.make_stack(); concept=ctl.concept("KEX")
        accepted=ctl.define_accepted(cluster,concept,Q)
        dirs=DirectoryCluster(root/"directory",cluster); self.addCleanup(dirs.stop); dirs.sync()
        ctl.reconcile_html(dirs,"DIR_ALPHA",accepted["coordinate"],root/"manifestation")
        p=root/"manifestation"/"concept.html"; p.write_text("<h1>corrupted visual</h1>")
        ctl.reconcile_html(dirs,"DIR_ALPHA",accepted["coordinate"],root/"manifestation")
        repaired=p.read_text()
        self.assertIn(concept.semantic_digest,repaired)
        self.assertEqual(dirs.resolve("DIR_ALPHA",accepted["coordinate"])["record"]["metadata"]["semantic_digest"],concept.semantic_digest)

if __name__=='__main__': unittest.main(verbosity=2)