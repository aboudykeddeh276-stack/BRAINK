import unittest

from observer2_runtime.ab_binary_codec import (
    ABBlock,
    canonicalize_tokens,
    decode_blocks,
    encode_bits,
    encode_tokens,
    metrics,
    pack_18_symbol,
    pack_alternating,
    parse_tokens,
    unpack_18_symbol,
    unpack_alternating,
)


class ABBinaryCodecTests(unittest.TestCase):
    def test_user_example_shape(self):
        bits = "111100011"
        self.assertEqual(encode_tokens(bits), "A4B3A2")
        self.assertEqual(decode_blocks(parse_tokens("A4B3A2")), bits)

    def test_run_over_nine_splits_canonically(self):
        self.assertEqual(encode_tokens("1" * 12), "A9A3")
        self.assertEqual(canonicalize_tokens("A9A3"), "A9A3")

    def test_zero_run(self):
        self.assertEqual(encode_tokens("000001"), "B5A1")

    def test_invalid_token_rejected(self):
        with self.assertRaises(ValueError):
            parse_tokens("A0")
        with self.assertRaises(ValueError):
            parse_tokens("C4")

    def test_18_symbol_wire_roundtrip(self):
        bits = "11110001100000111111111"
        blocks = encode_bits(bits)
        packed, count = pack_18_symbol(blocks)
        self.assertEqual(decode_blocks(unpack_18_symbol(packed, count)), bits)

    def test_alternating_wire_roundtrip(self):
        bits = "1111000110000011111"
        blocks = encode_bits(bits)
        packed, count = pack_alternating(blocks)
        self.assertEqual(decode_blocks(unpack_alternating(packed, count)), bits)

    def test_metrics_expose_representation_cost(self):
        m = metrics("111100011")
        self.assertEqual(m["raw_bits"], 9)
        self.assertEqual(m["canonical_blocks"], 3)
        self.assertEqual(m["ascii_token_chars"], 6)
        self.assertEqual(m["packed_18_symbol_bits"], 15)
        self.assertEqual(m["alternating_wire_bits"], 13)


if __name__ == "__main__":
    unittest.main()
