import unittest
from theorem_graph import (
    MasterTheoremGraphRegistry, 
    StrictBranchRouter, 
    BilateralCompressor,
    ParentTheoremNotFoundError, 
    GraphValidationError, 
    TensorViolationError
)

class TestRigorousTheoremGraph(unittest.TestCase):
    def test_missing_parent_raises_exception(self):
        registry = MasterTheoremGraphRegistry()
        with self.assertRaises(ParentTheoremNotFoundError):
            registry.register("CHILD_THM", {"tensor_min": 7.0}, parent_ids=["NON_EXISTENT_PARENT"])

    def test_tensor_violation_raises_exception(self):
        registry = MasterTheoremGraphRegistry()
        with self.assertRaises(TensorViolationError):
            registry.register("INVALID_TENSOR", {"tensor_min": 4.0}, [])

    def test_operator_inheritance_merging(self):
        registry = MasterTheoremGraphRegistry()
        registry.register("PARENT_A", {"tensor_min": 7.0}, parent_operators=["OP_1", "OP_2"])
        registry.register("PARENT_B", {"tensor_min": 8.0}, parent_operators=["OP_2", "OP_3"])
        
        child = registry.register("CHILD_C", {"tensor_min": 9.0}, parent_ids=["PARENT_A", "PARENT_B"])
        self.assertIn("OP_1", child.operators)
        self.assertIn("OP_2", child.operators)
        self.assertIn("OP_3", child.operators)
        self.assertEqual(len(child.operators), 3)

    def test_router_fails_loudly_on_unregistered_invariant(self):
        registry = MasterTheoremGraphRegistry()
        router = StrictBranchRouter(registry)
        with self.assertRaises(GraphValidationError):
            router.route("UNKNOWN_THM", {"sector": "cosmology", "resonance": 0.297})

    def test_router_fails_loudly_on_invalid_sector(self):
        registry = MasterTheoremGraphRegistry()
        registry.register("THM_1", {"tensor_min": 7.0}, parent_operators=["OP_1"])
        router = StrictBranchRouter(registry)
        with self.assertRaises(GraphValidationError):
            router.route("THM_1", {"sector": "INVALID_SECTOR", "resonance": 0.297})

    def test_router_computes_real_mutations(self):
        registry = MasterTheoremGraphRegistry()
        registry.register("THM_1", {"tensor_min": 7.0}, parent_operators=["OP_1"])
        router = StrictBranchRouter(registry)
        
        res1 = router.route("THM_1", {"sector": "cosmology", "resonance": 0.297})
        res2 = router.route("THM_1", {"sector": "cosmology", "resonance": 0.500})
        
        self.assertEqual(res1["status"], "VALIDATED_AND_ROUTED")
        self.assertNotEqual(res1["computed_metric"], res2["computed_metric"])

    def test_compressor_performs_actual_reduction(self):
        compressor = BilateralCompressor()
        res = compressor.compress("This is a comprehensive test sentence designed to verify that word counts and structural token extractions actively alter the compression output format.")
        self.assertIn("CLAIM[", res["compressed_form"])
        self.assertGreater(res["input_word_count"], 0)

if __name__ == "__main__":
    unittest.main()
