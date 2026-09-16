import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "client"))

from local_store import LocalStore


class LocalStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = LocalStore(Path(self.temp.name) / "client.db")
        self.location_id = "loc-sayville"
        self.store.cache_bootstrap(
            {
                "locations": [
                    {
                        "id": self.location_id,
                        "name": "Sayville",
                        "store_number": "5127",
                        "active": True,
                    }
                ],
                "employees": [
                    {
                        "id": "emp-1",
                        "name": "Nick",
                        "role": "admin",
                        "location_ids": [self.location_id],
                        "active": True,
                    }
                ],
            }
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_offline_save_calculations_and_outbox(self):
        customer_id = self.store.save_customer({"company": "Test Customer"})
        order_id = self.store.save_order(
            {
                "customer_id": customer_id,
                "location_id": self.location_id,
                "status": "New",
                "priority": "Rush",
                "received_date": "2026-09-16",
                "due_date": "2026-09-18",
                "tax_rate": 8.625,
                "discount": 10,
                "deposit": 25,
                "description": "Banner",
            },
            [{"item_name": "Banner", "quantity": 2, "unit_price": 50}],
        )
        self.assertEqual(self.store.pending_count(), 2)
        order = self.store.get_order(order_id)
        self.assertEqual(order["subtotal"], 100)
        self.assertAlmostEqual(order["total"], 97.76)
        self.assertAlmostEqual(order["balance"], 72.76)
        self.assertTrue(order["order_number"].startswith("WO-5127-"))

    def test_pin_cache(self):
        self.store.cache_employee_pin("emp-1", "246810")
        self.assertTrue(self.store.verify_cached_pin("emp-1", "246810"))
        self.assertFalse(self.store.verify_cached_pin("emp-1", "111111"))

    def test_conflict_resolution_keep_server(self):
        customer_id = self.store.save_customer({"company": "Local Name"})
        operation = self.store.pending_operations()[0]
        server = {
            "id": customer_id,
            "version": 2,
            "updated_at": "2026-09-16T12:00:00+00:00",
            "updated_by": "other",
            "is_deleted": False,
            "company": "Server Name",
            "first_name": "",
            "last_name": "",
            "phone": "",
            "email": "",
            "address1": "",
            "address2": "",
            "city": "",
            "state": "",
            "postal_code": "",
            "tax_exempt": False,
            "notes": "",
        }
        self.store.apply_push_results(
            [
                {
                    "operation_id": operation["operation_id"],
                    "entity_type": "customer",
                    "entity_id": customer_id,
                    "status": "conflict",
                    "server": server,
                    "message": "Version conflict",
                }
            ]
        )
        self.assertEqual(self.store.conflict_count(), 1)
        conflict = self.store.conflicts()[0]
        self.store.resolve_conflict(conflict["id"], "server")
        self.assertEqual(self.store.get_customer(customer_id)["company"], "Server Name")
        self.assertEqual(self.store.conflict_count(), 0)


if __name__ == "__main__":
    unittest.main()
