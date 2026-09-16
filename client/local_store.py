from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

APP_NAME = "PrintOrderManagerMultiStore"
PIN_ITERATIONS = 220_000
ORDER_STATUSES = (
    "Quote",
    "New",
    "Awaiting Artwork",
    "Proof Sent",
    "Proof Approved",
    "In Production",
    "Ready for Pickup",
    "Completed",
    "On Hold",
    "Cancelled",
)
PRIORITIES = ("Normal", "Rush", "High")


def app_data_dir() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = root / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


class LocalStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else app_data_dir() / "multistore_cache.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS locations (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, store_number TEXT NOT NULL,
                    timezone TEXT NOT NULL DEFAULT 'America/New_York', active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS employees (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
                    location_ids TEXT NOT NULL DEFAULT '[]', active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS employee_pin_cache (
                    employee_id TEXT PRIMARY KEY, verifier TEXT NOT NULL,
                    FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS customers (
                    id TEXT PRIMARY KEY, version INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT '', updated_by TEXT NOT NULL DEFAULT '',
                    is_deleted INTEGER NOT NULL DEFAULT 0, company TEXT NOT NULL DEFAULT '',
                    first_name TEXT NOT NULL DEFAULT '', last_name TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',
                    address1 TEXT NOT NULL DEFAULT '', address2 TEXT NOT NULL DEFAULT '',
                    city TEXT NOT NULL DEFAULT '', state TEXT NOT NULL DEFAULT '',
                    postal_code TEXT NOT NULL DEFAULT '', tax_exempt INTEGER NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY, version INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT '', updated_by TEXT NOT NULL DEFAULT '',
                    is_deleted INTEGER NOT NULL DEFAULT 0, customer_id TEXT NOT NULL,
                    location_id TEXT NOT NULL, order_number TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'New', priority TEXT NOT NULL DEFAULT 'Normal',
                    received_date TEXT NOT NULL DEFAULT '', due_date TEXT NOT NULL DEFAULT '',
                    assigned_to TEXT NOT NULL DEFAULT '', delivery_method TEXT NOT NULL DEFAULT 'Pickup',
                    po_number TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '',
                    artwork_path TEXT NOT NULL DEFAULT '', production_notes TEXT NOT NULL DEFAULT '',
                    customer_notes TEXT NOT NULL DEFAULT '', tax_rate REAL NOT NULL DEFAULT 0,
                    deposit REAL NOT NULL DEFAULT 0, discount REAL NOT NULL DEFAULT 0,
                    subtotal REAL NOT NULL DEFAULT 0, total REAL NOT NULL DEFAULT 0,
                    balance REAL NOT NULL DEFAULT 0, items TEXT NOT NULL DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, operation_id TEXT UNIQUE NOT NULL,
                    entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, action TEXT NOT NULL,
                    base_version INTEGER NOT NULL DEFAULT 0, payload TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT NOT NULL DEFAULT '', UNIQUE(entity_type, entity_id)
                );
                CREATE TABLE IF NOT EXISTS conflicts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL, local_payload TEXT NOT NULL, server_payload TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
                    UNIQUE(entity_type, entity_id)
                );
                CREATE INDEX IF NOT EXISTS idx_orders_location ON orders(location_id);
                CREATE INDEX IF NOT EXISTS idx_orders_due ON orders(due_date);
                CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
            """)
            conn.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('sync_cursor','0')")

    @staticmethod
    def now() -> str:
        return datetime.now().astimezone().replace(microsecond=0).isoformat()

    def get_meta(self, key: str, default: str = "") -> str:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
            return row[0] if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )

    def cache_bootstrap(self, data: dict) -> None:
        with self.connect() as conn:
            for loc in data.get("locations", []):
                conn.execute(
                    """
                    INSERT INTO locations(id,name,store_number,timezone,active) VALUES(?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET name=excluded.name,store_number=excluded.store_number,
                    timezone=excluded.timezone,active=excluded.active
                """,
                    (
                        loc["id"],
                        loc["name"],
                        loc["store_number"],
                        loc.get("timezone", "America/New_York"),
                        int(loc.get("active", True)),
                    ),
                )
            for emp in data.get("employees", []):
                self._upsert_employee(conn, emp)

    def _upsert_employee(self, conn: sqlite3.Connection, emp: dict) -> None:
        conn.execute(
            """
            INSERT INTO employees(id,name,role,location_ids,active,updated_at) VALUES(?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET name=excluded.name,role=excluded.role,
            location_ids=excluded.location_ids,active=excluded.active,updated_at=excluded.updated_at
        """,
            (
                emp["id"],
                emp["name"],
                emp["role"],
                json.dumps(emp.get("location_ids", [])),
                int(emp.get("active", True)),
                emp.get("updated_at", ""),
            ),
        )

    def locations(self) -> list[dict]:
        with self.connect() as conn:
            return [
                dict(x)
                for x in conn.execute("SELECT * FROM locations WHERE active=1 ORDER BY name")
            ]

    def employees(self, location_id: str = "", include_inactive: bool = False) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM employees ORDER BY name COLLATE NOCASE").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["location_ids"] = json.loads(item["location_ids"] or "[]")
            if not include_inactive and not item["active"]:
                continue
            if (
                location_id
                and item["role"] != "admin"
                and item["location_ids"]
                and location_id not in item["location_ids"]
            ):
                continue
            result.append(item)
        return result

    def cache_employee_pin(self, employee_id: str, pin: str) -> None:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, PIN_ITERATIONS)
        verifier = f"{PIN_ITERATIONS}${salt.hex()}${digest.hex()}"
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO employee_pin_cache(employee_id,verifier) VALUES(?,?) "
                "ON CONFLICT(employee_id) DO UPDATE SET verifier=excluded.verifier",
                (employee_id, verifier),
            )

    def verify_cached_pin(self, employee_id: str, pin: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT verifier FROM employee_pin_cache WHERE employee_id=?",
                (employee_id,),
            ).fetchone()
        if not row:
            return False
        try:
            iterations, salt, expected = row[0].split("$", 2)
            actual = hashlib.pbkdf2_hmac(
                "sha256", pin.encode(), bytes.fromhex(salt), int(iterations)
            )
            return hmac.compare_digest(actual, bytes.fromhex(expected))
        except (ValueError, TypeError):
            return False

    def list_customers(self, search: str = "") -> list[sqlite3.Row]:
        needle = f"%{search.strip()}%"
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT c.*,
                    TRIM(c.first_name || ' ' || c.last_name) contact_name,
                    (SELECT COUNT(*) FROM orders o WHERE o.customer_id=c.id AND o.is_deleted=0) order_count
                FROM customers c WHERE c.is_deleted=0 AND
                (?='%%' OR c.company LIKE ? OR c.first_name LIKE ? OR c.last_name LIKE ?
                 OR c.phone LIKE ? OR c.email LIKE ?)
                ORDER BY CASE WHEN c.company='' THEN c.last_name ELSE c.company END COLLATE NOCASE
            """,
                (needle, needle, needle, needle, needle, needle),
            ).fetchall()

    def get_customer(self, customer_id: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
            return dict(row) if row else None

    def save_customer(self, values: dict, customer_id: str | None = None) -> str:
        customer_id = customer_id or str(uuid.uuid4())
        fields = (
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
        with self.connect() as conn:
            old = conn.execute(
                "SELECT version FROM customers WHERE id=?", (customer_id,)
            ).fetchone()
            version = int(old[0]) if old else 0
            payload = {key: values.get(key, "") for key in fields}
            payload["tax_exempt"] = bool(values.get("tax_exempt", False))
            conn.execute(
                f"""
                INSERT INTO customers(id,version,updated_at,{",".join(fields)})
                VALUES(?,?,?,{",".join("?" for _ in fields)})
                ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at,is_deleted=0,
                {",".join(f"{key}=excluded.{key}" for key in fields)}
            """,
                (customer_id, version, self.now(), *(payload[k] for k in fields)),
            )
            self._queue(conn, "customer", customer_id, "upsert", version, payload)
        return customer_id

    def delete_customer(self, customer_id: str) -> None:
        self._delete_entity("customer", customer_id)

    def customer_choices(self) -> list[dict]:
        result = []
        for row in self.list_customers():
            display = row["company"]
            contact = row["contact_name"]
            if display and contact:
                display += f" — {contact}"
            elif not display:
                display = contact
            result.append({"id": row["id"], "display_name": display})
        return result

    def next_order_number(self, location_id: str) -> str:
        location = next((x for x in self.locations() if x["id"] == location_id), None)
        store = location["store_number"] if location else "STORE"
        suffix = uuid.uuid4().hex[:5].upper()
        return f"WO-{store}-{datetime.now():%y%m%d}-{suffix}"

    @staticmethod
    def calculate_order(values: dict, items: list[dict]) -> dict:
        clean_items, subtotal = [], 0.0
        for item in items:
            clean = dict(item)
            clean["quantity"] = max(float(clean.get("quantity", 0) or 0), 0)
            clean["unit_price"] = max(float(clean.get("unit_price", 0) or 0), 0)
            subtotal += clean["quantity"] * clean["unit_price"]
            clean_items.append(clean)
        discount = max(float(values.get("discount", 0) or 0), 0)
        deposit = max(float(values.get("deposit", 0) or 0), 0)
        tax_rate = max(float(values.get("tax_rate", 0) or 0), 0)
        total = max(subtotal - discount, 0) * (1 + tax_rate / 100)
        return {
            "items": clean_items,
            "subtotal": round(subtotal, 2),
            "total": round(total, 2),
            "balance": round(max(total - deposit, 0), 2),
        }

    def save_order(self, values: dict, items: list[dict], order_id: str | None = None) -> str:
        order_id = order_id or str(uuid.uuid4())
        fields = (
            "customer_id",
            "location_id",
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
        with self.connect() as conn:
            old = conn.execute(
                "SELECT version,order_number FROM orders WHERE id=?", (order_id,)
            ).fetchone()
            version = int(old["version"]) if old else 0
            if not values.get("order_number"):
                values["order_number"] = (
                    old["order_number"] if old else self.next_order_number(values["location_id"])
                )
            totals = self.calculate_order(values, items)
            payload = {key: values.get(key, "") for key in fields}
            payload.update(totals)
            db_fields = fields + ("subtotal", "total", "balance", "items")
            db_values = [json.dumps(payload[x]) if x == "items" else payload[x] for x in db_fields]
            conn.execute(
                f"""
                INSERT INTO orders(id,version,updated_at,{",".join(db_fields)})
                VALUES(?,?,?,{",".join("?" for _ in db_fields)})
                ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at,is_deleted=0,
                {",".join(f"{key}=excluded.{key}" for key in db_fields)}
            """,
                (order_id, version, self.now(), *db_values),
            )
            self._queue(
                conn,
                "order",
                order_id,
                "upsert",
                version,
                {k: v for k, v in payload.items() if k not in {"subtotal", "total", "balance"}},
            )
        return order_id

    def get_order(self, order_id: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT o.*,c.company,c.first_name,c.last_name,c.phone,c.email,c.address1,c.address2,
                       c.city,c.state,c.postal_code,l.name location_name,l.store_number
                FROM orders o JOIN customers c ON c.id=o.customer_id
                LEFT JOIN locations l ON l.id=o.location_id WHERE o.id=?
            """,
                (order_id,),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["items"] = json.loads(result["items"] or "[]")
        return result

    def list_orders(
        self,
        search: str = "",
        status: str = "All",
        location_id: str = "",
        due_filter: str = "All",
    ) -> list[sqlite3.Row]:
        clauses = ["o.is_deleted=0", "c.is_deleted=0"]
        args: list[Any] = []
        if search.strip():
            needle = f"%{search.strip()}%"
            clauses.append(
                "(o.order_number LIKE ? OR c.company LIKE ? OR c.first_name LIKE ? OR c.last_name LIKE ? OR o.description LIKE ?)"
            )
            args.extend([needle] * 5)
        if status != "All":
            clauses.append("o.status=?")
            args.append(status)
        if location_id:
            clauses.append("o.location_id=?")
            args.append(location_id)
        today = date.today().isoformat()
        if due_filter == "Overdue":
            clauses.append(
                "o.due_date<>'' AND o.due_date<? AND o.status NOT IN ('Completed','Cancelled')"
            )
            args.append(today)
        elif due_filter == "Due Today":
            clauses.append("o.due_date=?")
            args.append(today)
        elif due_filter == "Next 7 Days":
            clauses.append("o.due_date BETWEEN ? AND ?")
            args += [today, (date.today() + timedelta(days=7)).isoformat()]
        with self.connect() as conn:
            return conn.execute(
                f"""
                SELECT o.*,CASE WHEN c.company<>'' THEN c.company ELSE TRIM(c.first_name||' '||c.last_name) END customer_name,
                       l.name location_name,l.store_number
                FROM orders o JOIN customers c ON c.id=o.customer_id
                LEFT JOIN locations l ON l.id=o.location_id
                WHERE {" AND ".join(clauses)}
                ORDER BY CASE WHEN o.status IN ('Completed','Cancelled') THEN 1 ELSE 0 END,
                         CASE WHEN o.due_date='' THEN 1 ELSE 0 END,o.due_date,o.updated_at DESC
            """,
                args,
            ).fetchall()

    def delete_order(self, order_id: str) -> None:
        self._delete_entity("order", order_id)

    def _delete_entity(self, entity_type: str, entity_id: str) -> None:
        table = "customers" if entity_type == "customer" else "orders"
        with self.connect() as conn:
            row = conn.execute(f"SELECT version FROM {table} WHERE id=?", (entity_id,)).fetchone()
            if not row:
                return
            if int(row["version"]) == 0:
                conn.execute(
                    "DELETE FROM outbox WHERE entity_type=? AND entity_id=?",
                    (entity_type, entity_id),
                )
                conn.execute(f"DELETE FROM {table} WHERE id=?", (entity_id,))
                return
            conn.execute(
                f"UPDATE {table} SET is_deleted=1,updated_at=? WHERE id=?",
                (self.now(), entity_id),
            )
            self._queue(conn, entity_type, entity_id, "delete", int(row["version"]), {})

    def _queue(
        self,
        conn: sqlite3.Connection,
        entity_type: str,
        entity_id: str,
        action: str,
        base_version: int,
        payload: dict,
    ) -> None:
        existing = conn.execute(
            "SELECT operation_id,base_version FROM outbox WHERE entity_type=? AND entity_id=?",
            (entity_type, entity_id),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE outbox SET action=?,payload=?,created_at=?,attempts=0,last_error='' WHERE entity_type=? AND entity_id=?
            """,
                (action, json.dumps(payload), self.now(), entity_type, entity_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO outbox(operation_id,entity_type,entity_id,action,base_version,payload,created_at)
                VALUES(?,?,?,?,?,?,?)
            """,
                (
                    str(uuid.uuid4()),
                    entity_type,
                    entity_id,
                    action,
                    base_version,
                    json.dumps(payload),
                    self.now(),
                ),
            )

    def pending_operations(self, limit: int = 100) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM outbox ORDER BY sequence LIMIT ?", (limit,)
            ).fetchall()
        return [
            {
                "operation_id": row["operation_id"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "action": row["action"],
                "base_version": row["base_version"],
                "payload": json.loads(row["payload"]),
            }
            for row in rows
        ]

    def pending_count(self) -> int:
        with self.connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])

    def conflict_count(self) -> int:
        with self.connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0])

    def apply_push_results(self, results: Iterable[dict]) -> None:
        with self.connect() as conn:
            for result in results:
                op = conn.execute(
                    "SELECT * FROM outbox WHERE operation_id=?",
                    (result["operation_id"],),
                ).fetchone()
                if not op:
                    continue
                if result["status"] == "applied":
                    if result.get("server"):
                        self._apply_server(
                            conn,
                            result["entity_type"],
                            result["server"],
                            allow_pending=True,
                        )
                    conn.execute(
                        "DELETE FROM outbox WHERE operation_id=?",
                        (result["operation_id"],),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO conflicts(entity_type,entity_id,local_payload,server_payload,message,created_at)
                        VALUES(?,?,?,?,?,?) ON CONFLICT(entity_type,entity_id) DO UPDATE SET
                        local_payload=excluded.local_payload,server_payload=excluded.server_payload,
                        message=excluded.message,created_at=excluded.created_at
                    """,
                        (
                            op["entity_type"],
                            op["entity_id"],
                            op["payload"],
                            json.dumps(result.get("server") or {}),
                            result.get("message") or result["status"],
                            self.now(),
                        ),
                    )
                    conn.execute(
                        "DELETE FROM outbox WHERE operation_id=?",
                        (result["operation_id"],),
                    )

    def apply_events(self, events: Iterable[dict], cursor: int) -> None:
        with self.connect() as conn:
            for event in events:
                pending = conn.execute(
                    "SELECT 1 FROM outbox WHERE entity_type=? AND entity_id=?",
                    (event["entity_type"], event["entity_id"]),
                ).fetchone()
                if pending:
                    local = conn.execute(
                        "SELECT payload FROM outbox WHERE entity_type=? AND entity_id=?",
                        (event["entity_type"], event["entity_id"]),
                    ).fetchone()
                    conn.execute(
                        """
                        INSERT INTO conflicts(entity_type,entity_id,local_payload,server_payload,message,created_at)
                        VALUES(?,?,?,?,?,?) ON CONFLICT(entity_type,entity_id) DO NOTHING
                    """,
                        (
                            event["entity_type"],
                            event["entity_id"],
                            local[0],
                            json.dumps(event["payload"]),
                            "Another store changed this record while local edits were waiting",
                            self.now(),
                        ),
                    )
                    continue
                self._apply_server(conn, event["entity_type"], event["payload"])
            conn.execute(
                "INSERT INTO meta(key,value) VALUES('sync_cursor',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(cursor),),
            )

    def _apply_server(
        self,
        conn: sqlite3.Connection,
        entity_type: str,
        payload: dict,
        allow_pending: bool = False,
    ) -> None:
        if entity_type == "customer":
            fields = (
                "id",
                "version",
                "updated_at",
                "updated_by",
                "is_deleted",
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
            values = [
                int(payload.get(x, False))
                if x in {"is_deleted", "tax_exempt"}
                else payload.get(x, "")
                for x in fields
            ]
            conn.execute(
                f"INSERT INTO customers({','.join(fields)}) VALUES({','.join('?' for _ in fields)}) "
                f"ON CONFLICT(id) DO UPDATE SET {','.join(f'{x}=excluded.{x}' for x in fields if x != 'id')}",
                values,
            )
        elif entity_type == "order":
            fields = (
                "id",
                "version",
                "updated_at",
                "updated_by",
                "is_deleted",
                "customer_id",
                "location_id",
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
                "subtotal",
                "total",
                "balance",
                "items",
            )
            values = []
            for key in fields:
                value = payload.get(key, [] if key == "items" else "")
                if key == "items":
                    value = json.dumps(value)
                elif key == "is_deleted":
                    value = int(bool(value))
                values.append(value)
            conn.execute(
                f"INSERT INTO orders({','.join(fields)}) VALUES({','.join('?' for _ in fields)}) "
                f"ON CONFLICT(id) DO UPDATE SET {','.join(f'{x}=excluded.{x}' for x in fields if x != 'id')}",
                values,
            )

    def conflicts(self) -> list[dict]:
        with self.connect() as conn:
            return [
                dict(x) for x in conn.execute("SELECT * FROM conflicts ORDER BY created_at DESC")
            ]

    def resolve_conflict(self, conflict_id: int, choice: str) -> None:
        with self.connect() as conn:
            conflict = conn.execute("SELECT * FROM conflicts WHERE id=?", (conflict_id,)).fetchone()
            if not conflict:
                return
            server = json.loads(conflict["server_payload"] or "{}")
            local = json.loads(conflict["local_payload"] or "{}")
            if choice == "server":
                if server:
                    self._apply_server(conn, conflict["entity_type"], server, True)
            elif choice == "local":
                if not server:
                    raise ValueError(
                        "The server copy is unavailable; accept the server copy or recreate the record."
                    )
                self._apply_server(conn, conflict["entity_type"], server, True)
                self._queue(
                    conn,
                    conflict["entity_type"],
                    conflict["entity_id"],
                    "upsert",
                    int(server.get("version", 0)),
                    local,
                )
            conn.execute("DELETE FROM conflicts WHERE id=?", (conflict_id,))

    def dashboard(self, location_id: str = "") -> dict:
        args = [location_id, location_id]
        today = date.today().isoformat()
        week = (date.today() + timedelta(days=7)).isoformat()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) active,
                    SUM(CASE WHEN due_date<>'' AND due_date<? AND status NOT IN ('Completed','Cancelled') THEN 1 ELSE 0 END) overdue,
                    SUM(CASE WHEN due_date BETWEEN ? AND ? AND status NOT IN ('Completed','Cancelled') THEN 1 ELSE 0 END) due_soon,
                    SUM(CASE WHEN status='Ready for Pickup' THEN 1 ELSE 0 END) ready,
                    COALESCE(SUM(CASE WHEN status NOT IN ('Cancelled') THEN total ELSE 0 END),0) sales,
                    COALESCE(SUM(CASE WHEN status NOT IN ('Completed','Cancelled') THEN balance ELSE 0 END),0) outstanding
                FROM orders WHERE is_deleted=0 AND (?='' OR location_id=?) AND status NOT IN ('Completed','Cancelled')
            """,
                (today, today, week, *args),
            ).fetchone()
        return dict(row)

    def local_report(self, location_id: str = "") -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT l.name,l.store_number,COUNT(o.id) orders,COALESCE(SUM(o.total),0) sales,
                       COALESCE(SUM(CASE WHEN o.status NOT IN ('Completed','Cancelled') THEN o.balance ELSE 0 END),0) balance
                FROM locations l LEFT JOIN orders o ON o.location_id=l.id AND o.is_deleted=0
                WHERE (?='' OR l.id=?) GROUP BY l.id ORDER BY l.name
            """,
                (location_id, location_id),
            ).fetchall()
            return [dict(x) for x in rows]

    def backup(self, destination: str | Path) -> None:
        with (
            sqlite3.connect(self.path) as source,
            sqlite3.connect(destination) as target,
        ):
            source.backup(target)
