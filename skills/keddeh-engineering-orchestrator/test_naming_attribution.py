import unittest

from validate_naming_attribution import validate_naming_attribution


class NamingAttributionTests(unittest.TestCase):
    def test_naming_attribution_contract_is_valid(self) -> None:
        self.assertEqual(validate_naming_attribution(), [])


if __name__ == "__main__":
    unittest.main()
