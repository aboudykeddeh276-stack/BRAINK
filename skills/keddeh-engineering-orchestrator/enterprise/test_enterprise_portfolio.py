import unittest

from validate_enterprise_portfolio import validate


class EnterprisePortfolioTests(unittest.TestCase):
    def test_enterprise_portfolio_contract(self):
        self.assertEqual(validate(), [])


if __name__ == "__main__":
    unittest.main()
