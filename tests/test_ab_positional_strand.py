import unittest

from observer2_runtime.ab_positional_strand import (
    ABAuthorityRule,
    BODMAS_AUTHORITY_CHAIN,
    DOMAIN_C_TO_Z,
    build_line,
    build_line_strand,
    line_to_line_possibilities,
)


class ABPositionalRuleTests(unittest.TestCase):
    def test_rule_is_c_to_z_for_a(self):
        rule = ABAuthorityRule()
        a, _ = rule.resolve(x=1, authority_symbol="B")
        self.assertEqual(a, "C")
        self.assertEqual(rule.a_domain(), DOMAIN_C_TO_Z)

    def test_b_domain_removes_explicit_authority_when_present(self):
        rule = ABAuthorityRule()
        self.assertNotIn("O", rule.b_domain("O"))
        self.assertNotIn("D", rule.b_domain("D"))
        self.assertEqual(rule.b_domain("B"), DOMAIN_C_TO_Z)
        self.assertEqual(rule.b_domain("A"), DOMAIN_C_TO_Z)

    def test_rule_does_not_infer_authority_from_line_number(self):
        first = build_line(line_number=1,row=1,position=1,x=3,authority_symbol="M")
        second = build_line(line_number=2,row=1,position=2,x=3,authority_symbol="O")
        self.assertEqual(first.authority_symbol,"M")
        self.assertEqual(second.authority_symbol,"O")

    def test_line_to_line_hash_lineage(self):
        strand = build_line_strand(
            [(1,1,1,"B"),(1,2,2,"O"),(2,1,3,"D")],
            strand_id="proof",
        )
        self.assertEqual(strand.lines[0].previous_line_hash,"0"*64)
        self.assertEqual(strand.lines[1].previous_line_hash,strand.lines[0].line_hash)
        self.assertEqual(strand.lines[2].previous_line_hash,strand.lines[1].line_hash)
        self.assertEqual(strand.canonical()["rule_status"],"VALID_RULE")

    def test_possibilities_enumerate_bodmas_without_selecting_one(self):
        branches = line_to_line_possibilities(
            None,next_line_number=1,row=1,position=1,x=4
        )
        self.assertEqual(tuple(x.authority_symbol for x in branches),BODMAS_AUTHORITY_CHAIN)
        self.assertEqual(len(branches),6)
        self.assertEqual(len({x.line_hash for x in branches}),6)

    def test_next_line_possibilities_preserve_previous_line_identity(self):
        first = build_line(line_number=1,row=1,position=1,x=2,authority_symbol="O")
        branches = line_to_line_possibilities(
            first,next_line_number=2,row=1,position=2,x=5
        )
        self.assertTrue(all(x.previous_line_hash==first.line_hash for x in branches))

    def test_position_and_row_are_identity_not_authority_selection(self):
        a = build_line(line_number=1,row=1,position=1,x=2,authority_symbol="D")
        b = build_line(line_number=1,row=9,position=7,x=2,authority_symbol="D")
        self.assertEqual((a.a_symbol,a.b_symbol),(b.a_symbol,b.b_symbol))
        self.assertNotEqual(a.line_hash,b.line_hash)

    def test_authority_must_be_from_defined_chain(self):
        with self.assertRaises(ValueError):
            build_line(line_number=1,row=1,position=1,x=1,authority_symbol="Z")


if __name__ == "__main__":
    unittest.main()
