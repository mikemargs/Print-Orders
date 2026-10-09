import unittest
from datetime import UTC, date, datetime
from unittest.mock import patch

import test_assets_routes as assets_routes
import test_catalog_routes as catalog_routes
import test_operations_routes as operations_routes
from app.database import (
    CatalogProduct,
    Company,
    Customer,
    CustomerIssue,
    EquipmentAsset,
    InventoryItem,
    Location,
    Mailbox,
    OperationalTask,
    ShippingCase,
    WorkOrder,
)


class SummaryDrilldownTests(unittest.TestCase):
    tearDown = assets_routes.AssetRouteTests.tearDown
    login = assets_routes.AssetRouteTests.login

    def setUp(self):
        assets_routes.AssetRouteTests.setUp(self)
        with self.Session() as db:
            db.add(Company(id="other", name="Other", code="OTHER", password_hash="x"))
            db.flush()
            db.add_all(
                [
                    Customer(id="c1", company_id="co", company="First"),
                    Customer(id="c2", company_id="co", company="Second"),
                    Customer(id="foreign", company_id="other", company="Foreign"),
                    Location(
                        id="foreign-store", company_id="other", name="Foreign", store_number="1"
                    ),
                ]
            )
            db.get(Location, "l2").timezone = "Asia/Tokyo"
            db.commit()

    def add(self, model, id, **values):
        defaults = {"id": id, "company_id": "co", "location_id": "l1"}
        if model is not WorkOrder:
            defaults.update(created_by="s", updated_by="s")
        with self.Session() as db:
            db.add(model(**(defaults | values)))
            db.commit()

    def assert_view(self, path, key, view, expected, **filters):
        # A one-row page catches filters incorrectly applied after pagination.
        seen = []
        for offset in range(len(expected) + 1):
            response = self.client.get(
                path, params={"view": view, "limit": 1, "offset": offset} | filters
            )
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()
            self.assertEqual(data["total"], len(expected))
            seen.extend(row["id"] for row in data[key])
        self.assertCountEqual(seen, expected)

    def test_inventory_and_equipment_counts_are_complete_before_pagination(self):
        for id, quantity, active in [
            ("a", 20, True),
            ("b", 1, True),
            ("c", 0, True),
            ("d", 0, False),
        ]:
            self.add(InventoryItem, id, name=id, quantity=quantity, reorder_point=2, active=active)
        self.add(
            InventoryItem,
            "foreign",
            name="Foreign",
            company_id="other",
            location_id="foreign-store",
            quantity=0,
        )
        summary = self.client.get("/api/inventory/summary").json()
        self.assertEqual(summary["low_stock"], 2)
        self.assert_view("/api/inventory", "items", "low", ["b", "c"])
        self.assert_view("/api/inventory", "items", "out", ["c"])
        self.assert_view("/api/inventory", "items", "active", ["a", "b", "c"])
        for id, status in [
            ("a", "Operational"),
            ("b", "Needs Attention"),
            ("c", "Out of Service"),
            ("d", "Retired"),
        ]:
            self.add(
                EquipmentAsset, id, name=id, status=status, next_service_date=date(2026, 10, 8)
            )
        self.add(
            EquipmentAsset,
            "tokyo",
            name="Tokyo",
            location_id="l2",
            next_service_date=date(2026, 10, 9),
        )
        now = datetime(2026, 10, 9, 23, tzinfo=UTC)
        with (
            patch("app.services.drilldowns.utcnow", return_value=now),
            patch("app.routers.equipment.utcnow", return_value=now),
        ):
            self.assert_view(
                "/api/equipment", "equipment", "", ["a", "b", "c", "tokyo"], attention_only=True
            )
            self.assert_view("/api/equipment", "equipment", "attention", ["b", "c"])
            self.assert_view(
                "/api/equipment", "equipment", "service_overdue", ["a", "b", "c", "tokyo"]
            )
            self.assertEqual(self.client.get("/api/equipment/summary").json()["service_overdue"], 4)

    def test_mailbox_compliance_and_store_local_renewal_dates(self):
        complete = {
            "primary_id_on_file": True,
            "secondary_id_on_file": True,
            "form_1583_complete": True,
            "msa_complete": True,
            "phone_verified": True,
        }
        self.add(
            Mailbox,
            "a",
            mailbox_number="1",
            customer_id="c1",
            renewal_date=date(2026, 10, 9),
            **complete,
        )
        self.add(
            Mailbox,
            "b",
            mailbox_number="2",
            customer_id="c1",
            location_id="l2",
            renewal_date=date(2026, 10, 9),
        )
        self.add(
            Mailbox,
            "c",
            mailbox_number="3",
            customer_id="c2",
            renewal_date=date(2026, 11, 8),
            **complete,
        )
        self.add(
            Mailbox,
            "d",
            mailbox_number="4",
            customer_id="c1",
            status="Closed",
            renewal_date=date(2020, 1, 1),
        )
        self.add(Mailbox, "e", mailbox_number="5", customer_id="c1", renewal_date=None, **complete)
        now = datetime(2026, 10, 9, 23, tzinfo=UTC)
        with (
            patch("app.services.drilldowns.utcnow", return_value=now),
            patch("app.routers.mailboxes.utcnow", return_value=now),
        ):
            summary = self.client.get("/api/mailboxes/summary").json()
            self.assertEqual(summary["overdue"], 1)
            self.assertEqual(summary["due_30"], 2)
            self.assert_view("/api/mailboxes", "mailboxes", "overdue", ["b"])
            self.assert_view("/api/mailboxes", "mailboxes", "due_30", ["a", "c"])
            self.assert_view("/api/mailboxes", "mailboxes", "missing_compliance", ["b"])
            self.assert_view(
                "/api/mailboxes", "mailboxes", "active", ["a", "b", "e"], customer_id="c1"
            )

    def test_tasks_issues_and_shipping_ignore_closed_records(self):
        for model in [OperationalTask, CustomerIssue]:
            for id, status, priority, assignee in [
                ("a", "Open", "Normal", None),
                ("b", "Open", "Urgent", "s"),
                ("c", "Open", "High", "e"),
                ("d", "Resolved" if model is CustomerIssue else "Completed", "Urgent", "s"),
            ]:
                extra = {
                    "customer_id": "c1",
                    "title": id,
                    "status": status,
                    "priority": priority,
                    "assigned_employee_id": assignee,
                }
                if model is CustomerIssue:
                    extra.update(reference=id, description="", follow_up_date=date(2020, 1, 1))
                else:
                    extra.update(due_date=date(2020, 1, 1))
                self.add(model, id, **extra)
            path, key = (
                ("/api/issues", "issues") if model is CustomerIssue else ("/api/tasks", "tasks")
            )
            summary = self.client.get(path + "/summary").json()
            self.assertEqual(summary["high_priority"], 2)
            self.assertEqual(summary["assigned_to_me"], 1)
            self.assert_view(path, key, "high_priority", ["b", "c"])
            self.assert_view(path, key, "mine", ["b"])
            self.assert_view(path, key, "overdue", ["a", "b", "c"])
        for id, kind, status in [
            ("a", "GSR", "Open"),
            ("b", "Lost Package", "Open"),
            ("c", "Damage Claim", "Open"),
            ("d", "Shipping Claim", "Resolved"),
        ]:
            self.add(
                ShippingCase,
                id,
                tracking_number=id,
                customer_id="c1",
                case_type=kind,
                status=status,
                follow_up_date=date(2020, 1, 1),
            )
        self.assert_view("/api/shipping-cases", "cases", "gsr", ["a"])
        self.assert_view("/api/shipping-cases", "cases", "claims", ["b", "c"])
        self.assert_view("/api/shipping-cases", "cases", "overdue", ["a", "b", "c"])

    def test_company_and_customer_order_views(self):
        for id, status, priority in [
            ("a", "Completed", "Rush"),
            ("b", "Ready for Pickup", "Normal"),
            ("c", "New", "Rush"),
            ("d", "Cancelled", "Rush"),
        ]:
            self.add(
                WorkOrder,
                id,
                customer_id="c1",
                order_number=id,
                status=status,
                priority=priority,
                due_date="2020-01-01",
                balance=10,
            )
        self.add(WorkOrder, "deleted", customer_id="c1", order_number="deleted", is_deleted=True)
        self.add(
            WorkOrder,
            "foreign",
            company_id="other",
            location_id="foreign-store",
            customer_id="foreign",
            order_number="foreign",
        )
        self.add(WorkOrder, "second", location_id="l2", customer_id="c2", order_number="second")
        self.assert_view("/api/orders", "orders", "pending", ["b", "c", "second"])
        self.assert_view("/api/orders", "orders", "rush", ["c"])
        self.assert_view("/api/orders", "orders", "ready", ["b"])
        self.assert_view("/api/orders", "orders", "overdue", ["b", "c"])
        self.assert_view("/api/orders", "orders", "all", ["a", "b", "c", "d"], customer_id="c1")
        self.assert_view("/api/orders", "orders", "outstanding", ["a", "b", "c", "d"])
        self.assertEqual(self.client.get("/api/orders?view=unknown").status_code, 400)

    def test_customer_card_counts_are_not_capped_at_first_page(self):
        with self.Session() as db:
            db.add_all(
                [
                    WorkOrder(
                        id=f"o{i}",
                        company_id="co",
                        location_id="l1",
                        customer_id="c1",
                        order_number=str(i),
                        status="New",
                    )
                    for i in range(251)
                ]
            )
            db.commit()
        response = self.client.get("/api/customers/c1/summary")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["active_orders"], 251)
        self.assertEqual(response.json()["all_orders"], 251)
        self.assertEqual(self.client.get("/api/customers/foreign/summary").status_code, 404)


class CatalogDrilldownTests(unittest.TestCase):
    setUp = catalog_routes.CatalogRouteTests.setUp
    tearDown = catalog_routes.CatalogRouteTests.tearDown
    login = catalog_routes.CatalogRouteTests.login

    def test_pricing_views_and_category_counts_match_catalog_summary(self):
        summary = self.client.get("/api/catalog/summary").json()
        self.assertEqual(summary["tiered_products"], 12)
        self.assertEqual(summary["manual_price"], 16)
        for view, field in [
            ("tiered", "tiered_products"),
            ("manual", "manual_price"),
            ("active", "active_products"),
        ]:
            seen = []
            for offset in range(0, summary[field], 5):
                response = self.client.get(
                    "/api/catalog", params={"view": view, "limit": 5, "offset": offset}
                )
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                self.assertEqual(data["total"], summary[field])
                seen.extend(p["id"] for p in data["products"])
            self.assertEqual(len(set(seen)), summary[field])
        tiered = self.client.get("/api/catalog?view=tiered").json()["products"][0]
        with self.Session() as db:
            db.get(CatalogProduct, tiered["id"]).active = False
            db.commit()
        self.assertEqual(self.client.get("/api/catalog?view=tiered").json()["total"], 12)
        categories = self.client.get("/api/catalog/categories").json()
        self.assertEqual(len(categories["counts"]), summary["categories"])
        self.assertEqual(
            sum(c["count"] for c in categories["counts"]), summary["active_products"] - 1
        )
        for row in categories["counts"]:
            result = self.client.get(
                "/api/catalog", params={"view": "active", "category": row["category"], "limit": 1}
            ).json()
            self.assertEqual(result["total"], row["count"])


class ChecklistDrilldownTests(unittest.TestCase):
    setUp = operations_routes.OperationsRouteTests.setUp
    tearDown = operations_routes.OperationsRouteTests.tearDown
    login = operations_routes.OperationsRouteTests.login
    template_body = operations_routes.OperationsRouteTests.template_body
    create_template = operations_routes.OperationsRouteTests.create_template

    def test_all_stores_checklist_matches_summary_and_preserves_local_date(self):
        self.create_template(title="First")
        self.login("a", "admin", "l1")
        self.create_template(title="Second", location_id="l2")
        with self.Session() as db:
            db.get(Location, "l2").timezone = "Asia/Tokyo"
            db.commit()
        now = datetime(2026, 10, 9, 23, tzinfo=UTC)
        with patch("app.routers.operations.utcnow", return_value=now):
            response = self.client.get("/api/operations/checklist?location_id=all")
            self.assertEqual(response.status_code, 200, response.text)
            items = response.json()["items"]
            self.assertEqual(
                len(items), self.client.get("/api/operations/summary").json()["expected"]
            )
            self.assertEqual(
                {item["location_id"]: item["checklist_date"] for item in items},
                {"l1": "2026-10-09", "l2": "2026-10-10"},
            )
