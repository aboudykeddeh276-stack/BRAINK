import unittest

from observer2_runtime.ab_positional_strand import (
    ABAuthorityPolicy,
    BODMAS_AUTHORITY_CHAIN,
    DOMAIN_C_TO_Z,
    build_pair,
    build_strand,
    dna_projection,
    matrix_projection,
)


class ABPositionalStrandTests(unittest.TestCase):
    def test_pair_has_line_row_position_and_x_identity(self):
        pair = build_pair(line_number=1, row=2, position=3, x=4)
        self.assertEqual(pair.position.line_number, 1)
        self.assertEqual(pair.position.row, 2)
        self.assertEqual(pair.position.position, 3)
        self.assertEqual(pair.position.x, 4)
        self.assertEqual(len(pair.line_hash), 64)

    def test_a_selects_from_full_c_to_z_domain(self):
        policy = ABAuthorityPolicy()
        pair = build_pair(line_number=1, row=1, position=1, x=1, policy=policy)
        self.assertEqual(pair.a_symbol, "C")
        self.assertIn(pair.a_symbol, DOMAIN_C_TO_Z)

    def test_b_excludes_current_authority_symbol_when_in_domain(self):
        policy = ABAuthorityPolicy()
        # line 2 authority is O under BODMAS
        pair = build_pair(line_number=2, row=1, position=2, x=13, policy=policy)
        self.assertEqual(pair.authority_symbol, "O")
        self.assertNotEqual(pair.b_symbol, "O")

    def test_bodmas_chain_is_ordered_line_authority(self):
        policy = ABAuthorityPolicy()
        observed = [policy.authority_for_line(i) for i in range(1, 7)]
        self.assertEqual(tuple(observed), BODMAS_AUTHORITY_CHAIN)

    def test_strand_is_hash_linked_linearly_like_a_chain(self):
        strand = build_strand(
            [(1, 1, 1), (1, 2, 2), (1, 3, 3), (2, 1, 4)],
            strand_id="strand-1",
        )
        self.assertEqual(strand.lines[0].previous_line_hash, "0" * 64)
        self.assertEqual(strand.lines[1].previous_line_hash, strand.lines[0].line_hash)
        self.assertEqual(strand.lines[2].previous_line_hash, strand.lines[1].line_hash)
        self.assertEqual(len(strand.strand_hash), 64)

    def test_matrix_projection_preserves_rows_positions_and_lines(self):
        strand = build_strand(
            [(1, 2, 1), (1, 1, 2), (2, 1, 3)],
            strand_id="matrix",
        )
        rows = matrix_projection(strand)
        self.assertEqual([x["position"] for x in rows[1]], [1, 2])
        self.assertEqual(rows[2][0]["line_number"], 3)

    def test_dna_projection_preserves_linear_order(self):
        strand = build_strand(
            [(1, 1, 1), (1, 2, 2), (1, 3, 3)],
            strand_id="dna",
        )
        dna = dna_projection(strand)
        self.assertEqual([x["index"] for x in dna], [1, 2, 3])
        self.assertEqual(dna[1]["previous"], dna[0]["hash"])

    def test_custom_authority_chain_changes_b_domain_without_changing_model(self):
        policy = ABAuthorityPolicy(chain=("C", "D"))
        first = build_pair(line_number=1, row=1, position=1, x=1, policy=policy)
        second = build_pair(line_number=2, row=1, position=2, x=1, policy=policy)
        self.assertEqual(first.authority_symbol, "C")
        self.assertNotEqual(first.b_symbol, "C")
        self.assertEqual(second.authority_symbol, "D")
        self.assertNotEqual(second.b_symbol, "D")


if __name__ == "__main__":
    unittest.main()
