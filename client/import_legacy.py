"""Import the original single-computer Print Order Manager database.

Run while the multi-store client is closed. Imported records are placed in the
offline outbox and upload the next time an administrator or supervisor signs in.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from local_store import LocalStore


def import_database(source_path: Path, store_number: str, destination: LocalStore) -> dict:
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    location = next((x for x in destination.locations() if x["store_number"] == store_number), None)
    if not location:
        raise ValueError(
            f"Store #{store_number} is not cached on this computer. Connect the multi-store app first."
        )
    marker = f"legacy_import:{source_path.resolve()}:{source_path.stat().st_size}"
    if destination.get_meta(marker):
        raise ValueError("This exact legacy database has already been imported.")

    source = sqlite3.connect(source_path)
    source.row_factory = sqlite3.Row
    customer_map: dict[int, str] = {}
    customers = 0
    orders = 0
    try:
        for row in source.execute("SELECT * FROM customers WHERE 1=1 ORDER BY id"):
            available = set(row.keys())
            values = {
                key: row[key]
                for key in (
                    "company",
                    "first_name",
                    "last_name",
                    "phone",
                    "email",
                    "address1",
                    "address2",
                    "city",
                    "state",
                    "postal_code",
                    "tax_exempt",
                    "notes",
                )
                if key in available
            }
            customer_map[row["id"]] = destination.save_customer(values)
            customers += 1
        for row in source.execute("SELECT * FROM orders ORDER BY id"):
            available = set(row.keys())
            items = [
                dict(item)
                for item in source.execute(
                    "SELECT item_name,quantity,width,height,size_unit,sides,color,paper_material,finishing,unit_price,notes "
                    "FROM order_items WHERE order_id=? ORDER BY sort_order,id",
                    (row["id"],),
                )
            ]
            values = {
                key: row[key]
                for key in (
                    "order_number",
                    "status",
                    "priority",
                    "received_date",
                    "due_date",
                    "assigned_to",
                    "delivery_method",
                    "po_number",
                    "description",
                    "artwork_path",
                    "production_notes",
                    "customer_notes",
                    "tax_rate",
                    "deposit",
                    "discount",
                )
                if key in available
            }
            values["customer_id"] = customer_map[row["customer_id"]]
            values["location_id"] = location["id"]
            destination.save_order(values, items)
            orders += 1
    finally:
        source.close()
    destination.set_meta(marker, "completed")
    return {
        "customers": customers,
        "orders": orders,
        "pending": destination.pending_count(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the original Print Order Manager database")
    parser.add_argument("--database", required=True, type=Path, help="Path to print_orders.db")
    parser.add_argument(
        "--store",
        required=True,
        choices=("5127", "5345", "3167"),
        help="Store owning the imported orders",
    )
    args = parser.parse_args()
    result = import_database(args.database, args.store, LocalStore())
    print(json.dumps(result, indent=2))
    print("Import complete. Open the multi-store app and click Sync Now.")


if __name__ == "__main__":
    main()
