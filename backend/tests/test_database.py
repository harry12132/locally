import tempfile
import unittest
from pathlib import Path

from backend.database import find_invoices, initialize_database, search_contracts


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_dir.name) / "test.db"
        initialize_database(self.database)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_invoice_lookup_is_case_insensitive(self):
        invoices = find_invoices("smith & co", self.database)

        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices[0]["invoice_id"], "INV-102")
        self.assertEqual(invoices[0]["status"], "OVERDUE")

    def test_unknown_client_returns_no_invoices(self):
        self.assertEqual(find_invoices("Unknown Client", self.database), [])

    def test_contract_search_returns_local_clause(self):
        contracts = search_contracts("late payments interest", self.database)

        self.assertTrue(contracts)
        self.assertIn("2% interest", contracts[0]["content"])


if __name__ == "__main__":
    unittest.main()