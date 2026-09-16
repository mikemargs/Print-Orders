from __future__ import annotations

import html
import os
import threading
import tkinter as tk
import webbrowser
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk

from api_client import ApiClient, ApiError
from config import load_config, save_config
from local_store import ORDER_STATUSES, PRIORITIES, LocalStore, app_data_dir
from sync_engine import SyncWorker

APP_TITLE = "Print Order Manager — Multi-Store"
BG, NAV, BLUE, DARK_BLUE = "#f4f6f8", "#152b45", "#1f5fa8", "#174a82"
TEXT, MUTED, RED, GREEN, ORANGE = "#1d2733", "#617080", "#b42318", "#26734d", "#a15c00"


def money(value) -> str:
    try:
        return f"${float(value or 0):,.2f}"
    except (ValueError, TypeError):
        return "$0.00"


def to_number(value: str, label: str, blank: bool = False):
    text = value.strip().replace("$", "").replace(",", "")
    if blank and not text:
        return None
    try:
        return float(text or 0)
    except ValueError as exc:
        raise ValueError(f"{label} must be a number.") from exc


def iso_date(value: str, label: str, blank: bool = True) -> str:
    value = value.strip()
    if not value and blank:
        return ""
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{label} must use YYYY-MM-DD format.") from exc
    return value


class PrintOrderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.store = LocalStore()
        self.config_data = load_config()
        self.api = ApiClient(self.config_data["server_url"], self.config_data["company_token"])
        self.employee: dict = {}
        self.employee_pin = ""
        self.online = False
        self.sync_worker: SyncWorker | None = None
        self._styles()
        if not self.prepare_connection():
            self.destroy()
            return
        if not self.employee_sign_in():
            self.destroy()
            return
        self.build_main_window()
        self.deiconify()
        self.start_sync()

    def _styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("vista" if os.name == "nt" else "clam")
        except tk.TclError:
            pass
        style.configure(".", font=("Segoe UI", 10), foreground=TEXT)
        style.configure("Page.TFrame", background=BG)
        style.configure("Nav.TFrame", background=NAV)
        style.configure(
            "Brand.TLabel",
            background=NAV,
            foreground="white",
            font=("Segoe UI Semibold", 16),
        )
        style.configure(
            "NavInfo.TLabel", background=NAV, foreground="#b7c8da", font=("Segoe UI", 9)
        )
        style.configure("Nav.TButton", padding=(12, 10), anchor="w", font=("Segoe UI Semibold", 10))
        style.configure("Primary.TButton", padding=(10, 7), foreground="white", background=BLUE)
        style.map("Primary.TButton", background=[("active", DARK_BLUE)])
        style.configure(
            "Title.TLabel",
            background=BG,
            font=("Segoe UI Semibold", 22),
            foreground=TEXT,
        )
        style.configure("Subtitle.TLabel", background=BG, foreground=MUTED)
        style.configure("Card.TFrame", background="white", relief="solid", borderwidth=1)
        style.configure(
            "CardTitle.TLabel",
            background="white",
            foreground=MUTED,
            font=("Segoe UI Semibold", 9),
        )
        style.configure("Treeview", rowheight=29, fieldbackground="white", background="white")
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 9), padding=(5, 7))

    def prepare_connection(self) -> bool:
        if not self.config_data.get("company_token") or not self.config_data.get("location_id"):
            dialog = CompanySetupDialog(self, self.store, self.config_data)
            self.wait_window(dialog)
            if not dialog.result:
                return False
            self.config_data = dialog.result
            save_config(self.config_data)
            self.api = dialog.api
            self.online = True
            return True
        try:
            bootstrap = self.api.bootstrap()
            self.store.cache_bootstrap(bootstrap)
            self.online = True
            return True
        except ApiError as exc:
            if exc.status_code in (401, 403):
                dialog = CompanySetupDialog(self, self.store, self.config_data)
                self.wait_window(dialog)
                if not dialog.result:
                    return False
                self.config_data, self.api, self.online = (
                    dialog.result,
                    dialog.api,
                    True,
                )
                save_config(self.config_data)
                return True
            if self.store.locations() and self.store.employees(self.config_data["location_id"]):
                self.online = False
                return True
            messagebox.showerror(
                "Connection required",
                f"This computer has no offline data yet.\n\n{exc}",
                parent=self,
            )
            return False

    def employee_sign_in(self) -> bool:
        dialog = EmployeeLoginDialog(self, self.store, self.api, self.config_data, self.online)
        self.wait_window(dialog)
        if not dialog.result:
            return False
        self.employee, self.online, self.employee_pin = dialog.result
        return True

    def build_main_window(self):
        self.title(APP_TITLE)
        self.geometry("1380x840")
        self.minsize(1100, 700)
        self.configure(bg=BG)
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        self._menu()
        self.sidebar = ttk.Frame(self, style="Nav.TFrame", width=225)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.content = ttk.Frame(self, style="Page.TFrame")
        self.content.pack(side="left", fill="both", expand=True)
        ttk.Label(self.sidebar, text="PRINT ORDER\nMANAGER", style="Brand.TLabel").pack(
            anchor="w", padx=22, pady=(24, 8)
        )
        ttk.Label(
            self.sidebar,
            text=f"{self.config_data['location_name']}\nStore #{self.config_data['store_number']}",
            style="NavInfo.TLabel",
        ).pack(anchor="w", padx=22, pady=(0, 20))
        nav = [
            ("Dashboard", self.show_dashboard),
            ("Work Orders", self.show_orders),
            ("Customers", self.show_customers),
        ]
        if self.employee["role"] in ("supervisor", "admin"):
            nav.append(("Store Reports", self.show_reports))
        if self.employee["role"] == "admin":
            nav.append(("Employees", self.show_employees))
        nav.append(("Sync Issues", self.show_conflicts))
        for label, command in nav:
            ttk.Button(self.sidebar, text=label, command=command, style="Nav.TButton").pack(
                fill="x", padx=13, pady=3
            )
        ttk.Separator(self.sidebar).pack(fill="x", padx=16, pady=16)
        ttk.Button(
            self.sidebar,
            text="+ New Work Order",
            command=self.new_order,
            style="Primary.TButton",
        ).pack(fill="x", padx=17, pady=3)
        ttk.Button(self.sidebar, text="+ New Customer", command=self.new_customer).pack(
            fill="x", padx=17, pady=3
        )
        bottom = ttk.Frame(self.sidebar, style="Nav.TFrame")
        bottom.pack(side="bottom", fill="x", padx=18, pady=18)
        self.sync_label = ttk.Label(bottom, text="Starting sync…", style="NavInfo.TLabel")
        self.sync_label.pack(anchor="w")
        ttk.Label(
            bottom,
            text=f"{self.employee['name']} · {self.employee['role'].title()}",
            style="NavInfo.TLabel",
        ).pack(anchor="w", pady=(8, 0))
        ttk.Button(bottom, text="Sync Now", command=self.manual_sync).pack(fill="x", pady=(9, 0))
        self.current_search = None
        self.bind_all("<Control-n>", lambda _e: self.new_order())
        self.bind_all("<Control-f>", self.focus_search)
        self.show_dashboard()

    def _menu(self):
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="New Work Order\tCtrl+N", command=self.new_order)
        file_menu.add_command(label="New Customer", command=self.new_customer)
        file_menu.add_separator()
        file_menu.add_command(label="Sync Now", command=self.manual_sync)
        file_menu.add_command(label="Back Up Local Cache", command=self.backup_local_cache)
        file_menu.add_command(label="Open Local Data Folder", command=self.open_data_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close_app)
        menu.add_cascade(label="File", menu=file_menu)
        connection = tk.Menu(menu, tearoff=False)
        connection.add_command(label="Change Server or Store…", command=self.change_connection)
        menu.add_cascade(label="Connection", menu=connection)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(
            label="About",
            command=lambda: messagebox.showinfo(
                "About",
                "Print Order Manager — Multi-Store Edition\n\n"
                "Offline-capable customer and print-production tracking.",
            ),
        )
        menu.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menu)

    def backup_local_cache(self):
        filename = f"multistore_cache_{datetime.now():%Y-%m-%d_%H%M}.db"
        path = filedialog.asksaveasfilename(
            title="Back Up Local Cache",
            defaultextension=".db",
            filetypes=[("SQLite database", "*.db")],
            initialfile=filename,
        )
        if path:
            self.store.backup(path)
            messagebox.showinfo(
                "Local backup complete",
                "The offline cache was backed up. Central server backups are still required.",
            )

    def open_data_folder(self):
        folder = app_data_dir()
        if os.name == "nt":
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            webbrowser.open(folder.as_uri())

    def change_connection(self):
        if self.store.pending_count():
            messagebox.showwarning(
                "Pending changes",
                "Synchronize all pending changes before switching servers or stores.",
            )
            return
        dialog = CompanySetupDialog(self, self.store, self.config_data)
        self.wait_window(dialog)
        if dialog.result:
            save_config(dialog.result)
            messagebox.showinfo(
                "Connection updated",
                "The server/store setting was saved. Reopen the application to use it.",
            )
            self.close_app()

    def start_sync(self):
        if not self.online or not self.api.employee_token:
            self.update_sync_status(
                "offline",
                {
                    "pending": self.store.pending_count(),
                    "conflicts": self.store.conflict_count(),
                },
            )
            self.after(15000, self.retry_online)
            return
        self.sync_worker = SyncWorker(self.store, self.api, self.sync_callback)
        self.sync_worker.start()

    def retry_online(self):
        """Re-establish an employee session after an offline application start."""
        if not self.winfo_exists() or self.online or self.sync_worker:
            return

        def attempt():
            try:
                bootstrap = self.api.bootstrap()
                self.store.cache_bootstrap(bootstrap)
                data = self.api.employee_login(
                    self.employee["id"],
                    self.employee_pin,
                    self.config_data["location_id"],
                )
                self.store.cache_employee_pin(self.employee["id"], self.employee_pin)
                self.employee = data["employee"]
                self.after(0, self._connection_restored)
            except Exception:
                try:
                    self.after(20000, self.retry_online)
                except tk.TclError:
                    pass

        threading.Thread(target=attempt, daemon=True).start()

    def _connection_restored(self):
        self.online = True
        self.update_sync_status(
            "online",
            {
                "pending": self.store.pending_count(),
                "conflicts": self.store.conflict_count(),
            },
        )
        self.start_sync()

    def sync_callback(self, state: str, data: dict):
        try:
            self.after(0, lambda: self.update_sync_status(state, data))
        except tk.TclError:
            pass

    def update_sync_status(self, state: str, data: dict):
        self.online = state == "online"
        pending = data.get("pending", self.store.pending_count())
        conflicts = data.get("conflicts", self.store.conflict_count())
        if state == "online":
            text = f"● Online · {pending} waiting"
        else:
            text = f"● Offline · {pending} waiting"
        if conflicts:
            text += f" · {conflicts} issue(s)"
        if hasattr(self, "sync_label") and self.sync_label.winfo_exists():
            self.sync_label.configure(text=text)
        if hasattr(self, "status_banner") and self.status_banner.winfo_exists():
            self.status_banner.configure(
                text="Working offline — changes will sync automatically." if not self.online else ""
            )

    def manual_sync(self):
        if not self.api.employee_token:
            messagebox.showinfo(
                "Offline sign-in",
                "Sign out and sign in while connected before synchronizing.",
            )
            return
        if self.sync_worker:
            self.sync_worker.trigger()
        else:
            self.start_sync()

    def close_app(self):
        if self.sync_worker:
            self.sync_worker.stop()
        self.destroy()

    def clear(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.current_search = None

    def header(self, title: str, subtitle: str, action_text: str = "", action=None):
        header = ttk.Frame(self.content, style="Page.TFrame")
        header.pack(fill="x", padx=28, pady=(22, 12))
        left = ttk.Frame(header, style="Page.TFrame")
        left.pack(side="left")
        ttk.Label(left, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text=subtitle, style="Subtitle.TLabel").pack(anchor="w")
        if action_text:
            ttk.Button(header, text=action_text, command=action, style="Primary.TButton").pack(
                side="right"
            )
        self.status_banner = tk.Label(
            self.content,
            text="" if self.online else "Working offline — changes will sync automatically.",
            bg="#fff3cd",
            fg="#684f00",
            anchor="w",
            padx=12,
        )
        if not self.online:
            self.status_banner.pack(fill="x", padx=28, pady=(0, 8))

    def current_location_filter(self) -> str:
        return (
            ""
            if self.employee["role"] == "admin" and getattr(self, "all_locations", False)
            else self.config_data["location_id"]
        )

    def show_dashboard(self):
        self.clear()
        self.header(
            "Dashboard",
            "Current production status and balances.",
            "+ New Work Order",
            self.new_order,
        )
        data = self.store.dashboard(self.current_location_filter())
        cards = ttk.Frame(self.content, style="Page.TFrame")
        cards.pack(fill="x", padx=28, pady=5)
        values = [
            ("ACTIVE", data["active"], TEXT),
            ("DUE IN 7 DAYS", data["due_soon"] or 0, BLUE),
            ("OVERDUE", data["overdue"] or 0, RED),
            ("READY", data["ready"] or 0, GREEN),
            ("OUTSTANDING", money(data["outstanding"]), TEXT),
        ]
        for idx, (label, value, color) in enumerate(values):
            card = ttk.Frame(cards, style="Card.TFrame", padding=16)
            card.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 6, 0))
            cards.columnconfigure(idx, weight=1)
            ttk.Label(card, text=label, style="CardTitle.TLabel").pack(anchor="w")
            tk.Label(card, text=value, bg="white", fg=color, font=("Segoe UI Semibold", 20)).pack(
                anchor="w", pady=(6, 0)
            )
        ttk.Label(
            self.content,
            text="Upcoming Work",
            style="Title.TLabel",
            font=("Segoe UI Semibold", 14),
        ).pack(anchor="w", padx=28, pady=(22, 8))
        wrapper = ttk.Frame(self.content, style="Page.TFrame")
        wrapper.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        tree = self.order_tree_widget(wrapper)
        tree.pack(fill="both", expand=True)
        self.fill_order_tree(
            tree,
            self.store.list_orders(location_id=self.current_location_filter())[:18],
        )
        tree.bind("<Double-1>", lambda _e: self.edit_order_from(tree))

    def order_tree_widget(self, parent):
        cols = (
            "number",
            "location",
            "customer",
            "description",
            "status",
            "priority",
            "due",
            "total",
            "balance",
        )
        tree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse")
        for col, title, width in zip(
            cols,
            (
                "Work Order",
                "Store",
                "Customer",
                "Description",
                "Status",
                "Priority",
                "Due",
                "Total",
                "Balance",
            ),
            (145, 90, 155, 210, 140, 70, 90, 90, 90),
        ):
            tree.heading(col, text=title)
            tree.column(col, width=width, anchor="e" if col in ("total", "balance") else "w")
        tree.tag_configure("overdue", foreground=RED)
        return tree

    def fill_order_tree(self, tree, rows):
        tree.delete(*tree.get_children())
        today = date.today().isoformat()
        for row in rows:
            overdue = (
                row["due_date"]
                and row["due_date"] < today
                and row["status"] not in ("Completed", "Cancelled")
            )
            tree.insert(
                "",
                "end",
                iid=row["id"],
                values=(
                    row["order_number"],
                    row["store_number"],
                    row["customer_name"],
                    row["description"],
                    row["status"],
                    row["priority"],
                    row["due_date"] or "—",
                    money(row["total"]),
                    money(row["balance"]),
                ),
                tags=("overdue",) if overdue else (),
            )

    def show_orders(self):
        self.clear()
        self.header(
            "Work Orders",
            "Live across stores when online; changes queue safely when offline.",
            "+ New Work Order",
            self.new_order,
        )
        tools = ttk.Frame(self.content, style="Page.TFrame")
        tools.pack(fill="x", padx=28, pady=(0, 9))
        self.order_search, self.order_status, self.order_due = (
            tk.StringVar(),
            tk.StringVar(value="All"),
            tk.StringVar(value="All"),
        )
        search = ttk.Entry(tools, textvariable=self.order_search, width=31)
        search.pack(side="left")
        ttk.Combobox(
            tools,
            textvariable=self.order_status,
            values=("All", *ORDER_STATUSES),
            state="readonly",
            width=19,
        ).pack(side="left", padx=6)
        ttk.Combobox(
            tools,
            textvariable=self.order_due,
            values=("All", "Overdue", "Due Today", "Next 7 Days"),
            state="readonly",
            width=15,
        ).pack(side="left")
        self.location_filter = tk.StringVar(value="Current Store")
        if self.employee["role"] == "admin":
            ttk.Combobox(
                tools,
                textvariable=self.location_filter,
                values=("Current Store", "All Stores"),
                state="readonly",
                width=14,
            ).pack(side="left", padx=6)
        self.current_search = search
        wrapper = ttk.Frame(self.content, style="Page.TFrame")
        wrapper.pack(fill="both", expand=True, padx=28)
        self.orders_tree = self.order_tree_widget(wrapper)
        self.orders_tree.pack(fill="both", expand=True)
        self.orders_tree.bind("<Double-1>", lambda _e: self.edit_order_from(self.orders_tree))
        actions = ttk.Frame(self.content, style="Page.TFrame")
        actions.pack(fill="x", padx=28, pady=14)
        ttk.Button(
            actions, text="Edit", command=lambda: self.edit_order_from(self.orders_tree)
        ).pack(side="left")
        ttk.Button(actions, text="Print / Preview", command=self.preview_selected).pack(
            side="left", padx=6
        )
        if self.employee["role"] in ("supervisor", "admin"):
            ttk.Button(actions, text="Delete", command=self.delete_selected_order).pack(
                side="left", padx=6
            )
        for var in (
            self.order_search,
            self.order_status,
            self.order_due,
            self.location_filter,
        ):
            var.trace_add("write", lambda *_: self.after(120, self.refresh_orders))
        self.refresh_orders()

    def refresh_orders(self):
        if not hasattr(self, "orders_tree") or not self.orders_tree.winfo_exists():
            return
        location = (
            ""
            if self.employee["role"] == "admin" and self.location_filter.get() == "All Stores"
            else self.config_data["location_id"]
        )
        rows = self.store.list_orders(
            self.order_search.get(),
            self.order_status.get(),
            location,
            self.order_due.get(),
        )
        self.fill_order_tree(self.orders_tree, rows)

    def show_customers(self):
        self.clear()
        self.header(
            "Customers",
            "Company-wide customer directory.",
            "+ New Customer",
            self.new_customer,
        )
        tools = ttk.Frame(self.content, style="Page.TFrame")
        tools.pack(fill="x", padx=28, pady=(0, 9))
        self.customer_search = tk.StringVar()
        search = ttk.Entry(tools, textvariable=self.customer_search, width=40)
        search.pack(side="left")
        self.current_search = search
        cols = ("company", "contact", "phone", "email", "city", "orders")
        self.customer_tree = ttk.Treeview(
            self.content, columns=cols, show="headings", selectmode="browse"
        )
        for col, title, width in zip(
            cols,
            ("Company", "Contact", "Phone", "Email", "City", "Orders"),
            (220, 180, 135, 240, 150, 70),
        ):
            self.customer_tree.heading(col, text=title)
            self.customer_tree.column(col, width=width, anchor="center" if col == "orders" else "w")
        self.customer_tree.pack(fill="both", expand=True, padx=28)
        self.customer_tree.bind("<Double-1>", lambda _e: self.edit_selected_customer())
        actions = ttk.Frame(self.content, style="Page.TFrame")
        actions.pack(fill="x", padx=28, pady=14)
        ttk.Button(actions, text="Edit", command=self.edit_selected_customer).pack(side="left")
        ttk.Button(actions, text="Create Work Order", command=self.order_for_customer).pack(
            side="left", padx=6
        )
        if self.employee["role"] in ("supervisor", "admin"):
            ttk.Button(actions, text="Delete", command=self.delete_selected_customer).pack(
                side="left", padx=6
            )
        self.customer_search.trace_add("write", lambda *_: self.after(120, self.refresh_customers))
        self.refresh_customers()

    def refresh_customers(self):
        if not hasattr(self, "customer_tree") or not self.customer_tree.winfo_exists():
            return
        self.customer_tree.delete(*self.customer_tree.get_children())
        for row in self.store.list_customers(self.customer_search.get()):
            self.customer_tree.insert(
                "",
                "end",
                iid=row["id"],
                values=(
                    row["company"] or "—",
                    row["contact_name"] or "—",
                    row["phone"],
                    row["email"],
                    row["city"],
                    row["order_count"],
                ),
            )

    def show_reports(self):
        self.clear()
        self.header(
            "Store Reports",
            "Sales, order volume, and outstanding balances by location.",
        )
        rows = self.store.local_report("")
        cards = ttk.Frame(self.content, style="Page.TFrame")
        cards.pack(fill="x", padx=28, pady=8)
        for idx, row in enumerate(rows):
            card = ttk.Frame(cards, style="Card.TFrame", padding=18)
            card.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 8, 0))
            cards.columnconfigure(idx, weight=1)
            ttk.Label(
                card,
                text=f"{row['name']}  #{row['store_number']}",
                style="CardTitle.TLabel",
            ).pack(anchor="w")
            tk.Label(
                card,
                text=money(row["sales"]),
                bg="white",
                fg=TEXT,
                font=("Segoe UI Semibold", 20),
            ).pack(anchor="w", pady=(8, 2))
            ttk.Label(
                card,
                text=f"{row['orders']} orders · {money(row['balance'])} outstanding",
                style="CardTitle.TLabel",
            ).pack(anchor="w")
        ttk.Label(
            self.content,
            text="Reports use the records currently synchronized to this computer.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", padx=28, pady=18)

    def show_employees(self):
        self.clear()
        self.header(
            "Employees",
            "Manage employee PIN access and store permissions.",
            "+ Add Employee",
            self.add_employee,
        )
        cols = ("name", "role", "stores", "active")
        self.employee_tree = ttk.Treeview(
            self.content, columns=cols, show="headings", selectmode="browse"
        )
        for col, title, width in zip(
            cols, ("Employee", "Role", "Assigned Stores", "Active"), (220, 130, 440, 80)
        ):
            self.employee_tree.heading(col, text=title)
            self.employee_tree.column(col, width=width)
        self.employee_tree.pack(fill="both", expand=True, padx=28, pady=(6, 0))
        ttk.Button(self.content, text="Edit Selected", command=self.edit_employee).pack(
            anchor="w", padx=28, pady=14
        )
        self.refresh_employees()

    def refresh_employees(self):
        if not hasattr(self, "employee_tree") or not self.employee_tree.winfo_exists():
            return
        self.employee_tree.delete(*self.employee_tree.get_children())
        locations = {x["id"]: f"{x['name']} #{x['store_number']}" for x in self.store.locations()}
        for employee in self.store.employees(include_inactive=True):
            names = ", ".join(locations.get(x, x) for x in employee["location_ids"]) or "All stores"
            self.employee_tree.insert(
                "",
                "end",
                iid=employee["id"],
                values=(
                    employee["name"],
                    employee["role"].title(),
                    names,
                    "Yes" if employee["active"] else "No",
                ),
            )

    def add_employee(self):
        if not self.online:
            messagebox.showinfo(
                "Online connection required",
                "Employee permissions can only be changed while online.",
            )
            return
        EmployeeDialog(self, self.store, self.api, on_saved=self.employee_saved)

    def edit_employee(self):
        selected = self.employee_tree.selection()
        if selected:
            employee = next(
                (x for x in self.store.employees(include_inactive=True) if x["id"] == selected[0]),
                None,
            )
            if employee:
                EmployeeDialog(self, self.store, self.api, employee, self.employee_saved)

    def employee_saved(self, employee):
        self.store.cache_bootstrap({"employees": [employee]})
        self.refresh_employees()

    def show_conflicts(self):
        self.clear()
        self.header(
            "Sync Issues",
            "Review records changed at more than one store before synchronization.",
        )
        cols = ("type", "record", "message", "created")
        self.conflict_tree = ttk.Treeview(
            self.content, columns=cols, show="headings", selectmode="browse"
        )
        for col, title, width in zip(
            cols,
            ("Record Type", "Record ID", "Reason", "Detected"),
            (120, 280, 450, 180),
        ):
            self.conflict_tree.heading(col, text=title)
            self.conflict_tree.column(col, width=width)
        self.conflict_tree.pack(fill="both", expand=True, padx=28, pady=6)
        for row in self.store.conflicts():
            self.conflict_tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                values=(
                    row["entity_type"].title(),
                    row["entity_id"],
                    row["message"],
                    row["created_at"],
                ),
            )
        actions = ttk.Frame(self.content, style="Page.TFrame")
        actions.pack(fill="x", padx=28, pady=14)
        ttk.Button(
            actions,
            text="Accept Server Copy",
            command=lambda: self.resolve_conflict("server"),
        ).pack(side="left")
        if self.employee["role"] in ("supervisor", "admin"):
            ttk.Button(
                actions,
                text="Keep Local Copy",
                command=lambda: self.resolve_conflict("local"),
            ).pack(side="left", padx=6)

    def resolve_conflict(self, choice):
        selected = self.conflict_tree.selection()
        if not selected:
            messagebox.showinfo("Select an issue", "Select a sync issue first.")
            return
        text = (
            "replace the local record with the server copy"
            if choice == "server"
            else "send the local copy as the next version"
        )
        if messagebox.askyesno("Resolve sync issue", f"This will {text}. Continue?"):
            try:
                self.store.resolve_conflict(int(selected[0]), choice)
                self.show_conflicts()
                if self.sync_worker:
                    self.sync_worker.trigger()
            except ValueError as exc:
                messagebox.showerror("Cannot resolve", str(exc))

    def selected_id(self, tree) -> str | None:
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("Select a record", "Select a record first.")
            return None
        return selected[0]

    def new_customer(self):
        CustomerDialog(self, self.store, on_saved=self.after_customer)

    def edit_selected_customer(self):
        customer_id = self.selected_id(self.customer_tree)
        if customer_id:
            CustomerDialog(self, self.store, customer_id, self.after_customer)

    def after_customer(self, _id):
        if hasattr(self, "customer_tree") and self.customer_tree.winfo_exists():
            self.refresh_customers()
        if self.sync_worker:
            self.sync_worker.trigger()

    def delete_selected_customer(self):
        customer_id = self.selected_id(self.customer_tree)
        if customer_id and messagebox.askyesno(
            "Delete customer", "Delete this customer across all stores?"
        ):
            self.store.delete_customer(customer_id)
            self.refresh_customers()
            if self.sync_worker:
                self.sync_worker.trigger()

    def order_for_customer(self):
        customer_id = self.selected_id(self.customer_tree)
        if customer_id:
            self.new_order(customer_id)

    def new_order(self, customer_id: str | None = None):
        if not self.store.customer_choices():
            messagebox.showinfo(
                "Customer needed",
                "Add a customer before creating the first work order.",
            )
            self.new_customer()
            return
        OrderDialog(
            self,
            self.store,
            self.config_data["location_id"],
            customer_id=customer_id,
            on_saved=self.after_order,
        )

    def edit_order_from(self, tree):
        order_id = self.selected_id(tree)
        if order_id:
            OrderDialog(
                self,
                self.store,
                self.config_data["location_id"],
                order_id=order_id,
                on_saved=self.after_order,
            )

    def after_order(self, _id):
        if hasattr(self, "orders_tree") and self.orders_tree.winfo_exists():
            self.refresh_orders()
        if self.sync_worker:
            self.sync_worker.trigger()

    def delete_selected_order(self):
        order_id = self.selected_id(self.orders_tree)
        if order_id and messagebox.askyesno(
            "Delete work order", "Delete this work order across all stores?"
        ):
            self.store.delete_order(order_id)
            self.refresh_orders()
            if self.sync_worker:
                self.sync_worker.trigger()

    def preview_selected(self):
        order_id = self.selected_id(self.orders_tree)
        if order_id:
            self.preview_order(order_id)

    def preview_order(self, order_id: str):
        order = self.store.get_order(order_id)
        if not order:
            return
        esc = lambda x: html.escape(str(x or ""))
        items = "".join(
            f"<tr><td>{esc(x.get('item_name'))}</td><td>{float(x.get('quantity', 0)):g}</td><td>{esc(item_spec(x))}</td><td class='n'>{money(x.get('unit_price'))}</td><td class='n'>{money(float(x.get('quantity', 0)) * float(x.get('unit_price', 0)))}</td></tr>"
            for x in order["items"]
        )
        customer = order["company"] or f"{order['first_name']} {order['last_name']}".strip()
        page = f"""<!doctype html><meta charset='utf-8'><title>{esc(order["order_number"])}</title><style>
        body{{font:13px Segoe UI,Arial;color:#1d2733;margin:32px}}header{{display:flex;justify-content:space-between;border-bottom:4px solid #1f5fa8;padding-bottom:12px}}h1{{margin:0;color:#1f5fa8}}table{{border-collapse:collapse;width:100%;margin-top:15px}}th{{background:#eaf3fc;text-align:left}}th,td{{padding:8px;border-bottom:1px solid #ddd}}.n{{text-align:right}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:25px;margin-top:20px}}.totals{{width:330px;margin-left:auto}}.notes{{white-space:pre-wrap;border:1px solid #ccc;padding:10px;min-height:45px}}@media print{{body{{margin:12mm}}.tip{{display:none}}}}</style>
        <header><div><h1>PRINT WORK ORDER</h1><b>{esc(order["location_name"])} #{esc(order["store_number"])}</b></div><div><b>{esc(order["order_number"])}</b><br>{esc(order["status"])}<br>Priority: {esc(order["priority"])}</div></header>
        <div class='grid'><div><b>Customer</b><br>{esc(customer)}<br>{esc(order["phone"])}<br>{esc(order["email"])}</div><div><b>Received:</b> {esc(order["received_date"])}<br><b>Due:</b> {esc(order["due_date"] or "Not set")}<br><b>Assigned:</b> {esc(order["assigned_to"])}<br><b>Delivery:</b> {esc(order["delivery_method"])}</div></div>
        <h2>{esc(order["description"] or "Order Items")}</h2><table><tr><th>Item</th><th>Qty</th><th>Specifications</th><th>Unit</th><th>Amount</th></tr>{items}</table>
        <table class='totals'><tr><td>Subtotal</td><td class='n'>{money(order["subtotal"])}</td></tr><tr><td>Discount</td><td class='n'>-{money(order["discount"])}</td></tr><tr><td>Tax</td><td class='n'>{money(order["total"] - (max(order["subtotal"] - order["discount"], 0)))}</td></tr><tr><td><b>Total</b></td><td class='n'><b>{money(order["total"])}</b></td></tr><tr><td>Deposit</td><td class='n'>-{money(order["deposit"])}</td></tr><tr><td><b>Balance</b></td><td class='n'><b>{money(order["balance"])}</b></td></tr></table>
        <h3>Production Notes</h3><div class='notes'>{esc(order["production_notes"])}</div><h3>Customer Notes</h3><div class='notes'>{esc(order["customer_notes"])}</div><p class='tip'>Press Ctrl+P to print or save as PDF.</p>"""
        path = app_data_dir() / f"{order['order_number']}.html"
        path.write_text(page, encoding="utf-8")
        webbrowser.open(path.as_uri())

    def focus_search(self, _e=None):
        if self.current_search and self.current_search.winfo_exists():
            self.current_search.focus_set()


class CompanySetupDialog(tk.Toplevel):
    def __init__(self, parent, store: LocalStore, existing: dict):
        super().__init__(parent)
        self.store, self.existing, self.result = store, existing, None
        self.api = ApiClient(existing.get("server_url", "http://localhost:8000"))
        self.title("Connect This Store")
        self.geometry("610x520")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.grab_set()
        frame = ttk.Frame(self, padding=26)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Connect This Store", font=("Segoe UI Semibold", 20)).pack(anchor="w")
        ttk.Label(
            frame,
            text="Enter the address and shared company credentials supplied by the administrator.",
            wraplength=530,
        ).pack(anchor="w", pady=(4, 18))
        self.server = tk.StringVar(value=existing.get("server_url") or "http://localhost:8000")
        self.code = tk.StringVar(value=existing.get("company_code") or "UPS-PRINT")
        self.password = tk.StringVar()
        self.location = tk.StringVar()
        for label, var, show in (
            ("Server address", self.server, ""),
            ("Company code", self.code, ""),
            ("Company password", self.password, "•"),
        ):
            ttk.Label(frame, text=label).pack(anchor="w", pady=(7, 2))
            ttk.Entry(frame, textvariable=var, show=show).pack(fill="x")
        ttk.Button(frame, text="Connect", command=self.connect, style="Primary.TButton").pack(
            anchor="w", pady=14
        )
        ttk.Label(frame, text="Store location").pack(anchor="w", pady=(5, 2))
        self.location_box = ttk.Combobox(frame, textvariable=self.location, state="readonly")
        self.location_box.pack(fill="x")
        self.status = ttk.Label(frame, text="", foreground=MUTED)
        self.status.pack(anchor="w", pady=8)
        buttons = ttk.Frame(frame)
        buttons.pack(side="bottom", fill="x")
        ttk.Button(buttons, text="Cancel", command=self.cancel).pack(side="right", padx=6)
        self.save_button = ttk.Button(
            buttons, text="Save and Continue", command=self.save, state="disabled"
        )
        self.save_button.pack(side="right")
        self.locations: dict[str, dict] = {}

    def connect(self):
        try:
            self.status.configure(text="Connecting…")
            self.update_idletasks()
            self.api = ApiClient(self.server.get())
            auth = self.api.company_login(self.code.get(), self.password.get())
            bootstrap = self.api.bootstrap()
            self.store.cache_bootstrap(bootstrap)
            self.locations = {
                f"{x['name']} — Store #{x['store_number']}": x for x in bootstrap["locations"]
            }
            self.location_box.configure(values=list(self.locations))
            old = next(
                (
                    name
                    for name, loc in self.locations.items()
                    if loc["id"] == self.existing.get("location_id")
                ),
                "",
            )
            self.location.set(old or (next(iter(self.locations)) if self.locations else ""))
            self.company = auth["company"]
            self.status.configure(text="Connected successfully.", foreground=GREEN)
            self.save_button.configure(state="normal")
        except Exception as exc:
            self.status.configure(text=str(exc), foreground=RED)
            self.save_button.configure(state="disabled")

    def save(self):
        loc = self.locations.get(self.location.get())
        if not loc:
            messagebox.showerror(
                "Store required", "Select this computer's store location.", parent=self
            )
            return
        self.result = {
            "server_url": self.api.base_url,
            "company_code": self.company["code"],
            "company_name": self.company["name"],
            "company_token": self.api.company_token,
            "location_id": loc["id"],
            "location_name": loc["name"],
            "store_number": loc["store_number"],
        }
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


class EmployeeLoginDialog(tk.Toplevel):
    def __init__(self, parent, store: LocalStore, api: ApiClient, config: dict, online: bool):
        super().__init__(parent)
        self.store, self.api, self.config, self.online, self.result = (
            store,
            api,
            config,
            online,
            None,
        )
        self.title("Employee Sign In")
        self.geometry("470x360")
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        frame = ttk.Frame(self, padding=28)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Employee Sign In", font=("Segoe UI Semibold", 20)).pack(anchor="w")
        ttk.Label(frame, text=f"{config['location_name']} — Store #{config['store_number']}").pack(
            anchor="w", pady=(3, 18)
        )
        employees = store.employees(config["location_id"])
        self.employee_map = {f"{x['name']} — {x['role'].title()}": x for x in employees}
        self.employee_name, self.pin = tk.StringVar(), tk.StringVar()
        ttk.Label(frame, text="Employee").pack(anchor="w")
        box = ttk.Combobox(
            frame,
            textvariable=self.employee_name,
            values=list(self.employee_map),
            state="readonly",
        )
        box.pack(fill="x", pady=(2, 12))
        if employees:
            self.employee_name.set(next(iter(self.employee_map)))
        ttk.Label(frame, text="PIN").pack(anchor="w")
        pin_entry = ttk.Entry(frame, textvariable=self.pin, show="•")
        pin_entry.pack(fill="x", pady=(2, 8))
        pin_entry.bind("<Return>", lambda _e: self.sign_in())
        self.status = ttk.Label(
            frame,
            text="Online" if online else "Offline sign-in",
            foreground=GREEN if online else ORANGE,
        )
        self.status.pack(anchor="w")
        buttons = ttk.Frame(frame)
        buttons.pack(side="bottom", fill="x")
        ttk.Button(buttons, text="Cancel", command=self.cancel).pack(side="right", padx=6)
        ttk.Button(buttons, text="Sign In", command=self.sign_in, style="Primary.TButton").pack(
            side="right"
        )

    def sign_in(self):
        employee = self.employee_map.get(self.employee_name.get())
        if not employee or not self.pin.get():
            messagebox.showerror(
                "Sign-in required", "Select your name and enter your PIN.", parent=self
            )
            return
        if self.online:
            try:
                data = self.api.employee_login(
                    employee["id"], self.pin.get(), self.config["location_id"]
                )
                self.store.cache_employee_pin(employee["id"], self.pin.get())
                self.result = (data["employee"], True, self.pin.get())
                self.destroy()
                return
            except ApiError as exc:
                if exc.status_code:
                    messagebox.showerror("Sign-in failed", str(exc), parent=self)
                    return
        if self.store.verify_cached_pin(employee["id"], self.pin.get()):
            self.result = (employee, False, self.pin.get())
            self.destroy()
        else:
            messagebox.showerror(
                "Offline sign-in unavailable",
                "This employee must sign in successfully online on this computer before offline sign-in can be used.",
                parent=self,
            )

    def cancel(self):
        self.result = None
        self.destroy()


class CustomerDialog(tk.Toplevel):
    def __init__(self, parent, store, customer_id=None, on_saved=None):
        super().__init__(parent)
        self.store, self.customer_id, self.on_saved = store, customer_id, on_saved
        self.title("Edit Customer" if customer_id else "New Customer")
        self.geometry("650x650")
        self.transient(parent)
        self.grab_set()
        self.vars = {
            x: tk.StringVar()
            for x in (
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
            )
        }
        self.tax_exempt = tk.BooleanVar()
        f = ttk.Frame(self, padding=20)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="Customer Details", font=("Segoe UI Semibold", 18)).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 12)
        )
        fields = [
            ("Company", "company", 1, 0, 3),
            ("First name", "first_name", 3, 0, 1),
            ("Last name", "last_name", 3, 2, 1),
            ("Phone", "phone", 5, 0, 1),
            ("Email", "email", 5, 2, 1),
            ("Address", "address1", 7, 0, 3),
            ("Address line 2", "address2", 9, 0, 3),
            ("City", "city", 11, 0, 1),
            ("State", "state", 11, 2, 1),
            ("ZIP / Postal", "postal_code", 13, 0, 1),
        ]
        for label, key, row, col, span in fields:
            ttk.Label(f, text=label).grid(
                row=row, column=col, columnspan=span, sticky="w", pady=(4, 2)
            )
            ttk.Entry(f, textvariable=self.vars[key]).grid(
                row=row + 1,
                column=col,
                columnspan=span,
                sticky="ew",
                padx=(0, 12 if col == 0 else 0),
            )
        f.columnconfigure(0, weight=1)
        f.columnconfigure(2, weight=1)
        ttk.Checkbutton(f, text="Tax exempt", variable=self.tax_exempt).grid(
            row=14, column=2, sticky="w"
        )
        ttk.Label(f, text="Notes").grid(row=15, column=0, sticky="w", pady=(8, 2))
        self.notes = tk.Text(f, height=6, wrap="word", font=("Segoe UI", 10))
        self.notes.grid(row=16, column=0, columnspan=4, sticky="nsew")
        f.rowconfigure(16, weight=1)
        b = ttk.Frame(f)
        b.grid(row=17, column=0, columnspan=4, sticky="e", pady=(13, 0))
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="left", padx=5)
        ttk.Button(b, text="Save Customer", command=self.save, style="Primary.TButton").pack(
            side="left"
        )
        if customer_id:
            row = store.get_customer(customer_id)
            if row:
                for k, v in self.vars.items():
                    v.set(row[k])
                self.tax_exempt.set(bool(row["tax_exempt"]))
                self.notes.insert("1.0", row["notes"])

    def save(self):
        values = {k: v.get().strip() for k, v in self.vars.items()}
        if not values["company"] and not values["first_name"] and not values["last_name"]:
            messagebox.showerror("Name required", "Enter a company or contact name.", parent=self)
            return
        values.update(
            tax_exempt=int(self.tax_exempt.get()),
            notes=self.notes.get("1.0", "end-1c").strip(),
        )
        result = self.store.save_customer(values, self.customer_id)
        if self.on_saved:
            self.on_saved(result)
        self.destroy()


def item_spec(item: dict) -> str:
    parts = []
    if item.get("width") is not None and item.get("height") is not None:
        parts.append(
            f"{float(item['width']):g} × {float(item['height']):g} {item.get('size_unit', 'in')}"
        )
    parts.extend(
        str(item.get(k))
        for k in ("sides", "color", "paper_material", "finishing", "notes")
        if item.get(k)
    )
    return " • ".join(parts)


class ItemDialog(tk.Toplevel):
    def __init__(self, parent, item=None, on_saved=None):
        super().__init__(parent)
        self.on_saved = on_saved
        self.title("Edit Line Item" if item else "Add Line Item")
        self.geometry("640x590")
        self.transient(parent)
        self.grab_set()
        keys = (
            "item_name",
            "quantity",
            "width",
            "height",
            "size_unit",
            "sides",
            "color",
            "paper_material",
            "finishing",
            "unit_price",
        )
        self.vars = {x: tk.StringVar() for x in keys}
        self.vars["quantity"].set("1")
        self.vars["size_unit"].set("in")
        self.vars["unit_price"].set("0.00")
        f = ttk.Frame(self, padding=20)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="Print Item", font=("Segoe UI Semibold", 18)).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 12)
        )
        fields = [
            ("Item / Product *", "item_name", 1, 0, 4),
            ("Quantity *", "quantity", 3, 0, 1),
            ("Unit price *", "unit_price", 3, 2, 1),
            ("Width", "width", 5, 0, 1),
            ("Height", "height", 5, 2, 1),
            ("Unit", "size_unit", 7, 0, 1),
            ("Sides", "sides", 7, 2, 1),
            ("Color", "color", 9, 0, 1),
            ("Paper / Material", "paper_material", 9, 2, 1),
            ("Finishing", "finishing", 11, 0, 4),
        ]
        for label, key, row, col, span in fields:
            ttk.Label(f, text=label).grid(
                row=row, column=col, columnspan=span, sticky="w", pady=(4, 2)
            )
            values = {
                "size_unit": ("in", "ft", "mm", "cm"),
                "sides": ("", "Single-sided", "Double-sided"),
                "color": ("", "Full Color", "Black & White", "Spot Color"),
            }.get(key)
            widget = (
                ttk.Combobox(
                    f,
                    textvariable=self.vars[key],
                    values=values,
                    state="readonly" if key == "size_unit" else "normal",
                )
                if values
                else ttk.Entry(f, textvariable=self.vars[key])
            )
            widget.grid(
                row=row + 1,
                column=col,
                columnspan=span,
                sticky="ew",
                padx=(0, 12 if col == 0 else 0),
            )
        f.columnconfigure(0, weight=1)
        f.columnconfigure(2, weight=1)
        ttk.Label(f, text="Item notes").grid(row=13, column=0, sticky="w", pady=(8, 2))
        self.notes = tk.Text(f, height=5, wrap="word", font=("Segoe UI", 10))
        self.notes.grid(row=14, column=0, columnspan=4, sticky="nsew")
        f.rowconfigure(14, weight=1)
        b = ttk.Frame(f)
        b.grid(row=15, column=0, columnspan=4, sticky="e", pady=(12, 0))
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="left", padx=5)
        ttk.Button(b, text="Save Item", command=self.save, style="Primary.TButton").pack(
            side="left"
        )
        if item:
            for k, v in self.vars.items():
                value = item.get(k, "")
                v.set("" if value is None else str(value))
            self.notes.insert("1.0", item.get("notes", ""))

    def save(self):
        try:
            if not self.vars["item_name"].get().strip():
                raise ValueError("Item / Product is required.")
            qty = to_number(self.vars["quantity"].get(), "Quantity")
            price = to_number(self.vars["unit_price"].get(), "Unit price")
            width = to_number(self.vars["width"].get(), "Width", True)
            height = to_number(self.vars["height"].get(), "Height", True)
            if qty <= 0 or price < 0:
                raise ValueError("Quantity must be positive and price cannot be negative.")
            item = {k: v.get().strip() for k, v in self.vars.items()}
            item.update(
                quantity=qty,
                unit_price=price,
                width=width,
                height=height,
                notes=self.notes.get("1.0", "end-1c").strip(),
            )
            self.on_saved(item)
            self.destroy()
        except ValueError as exc:
            messagebox.showerror("Check item", str(exc), parent=self)


class OrderDialog(tk.Toplevel):
    def __init__(
        self,
        parent: PrintOrderApp,
        store,
        current_location_id,
        order_id=None,
        customer_id=None,
        on_saved=None,
    ):
        super().__init__(parent)
        (
            self.parent_app,
            self.store,
            self.current_location_id,
            self.order_id,
            self.on_saved,
        ) = parent, store, current_location_id, order_id, on_saved
        self.title("Edit Work Order" if order_id else "New Work Order")
        self.geometry("1030x810")
        self.minsize(890, 680)
        self.transient(parent)
        self.grab_set()
        self.items = []
        self.order_location_id = current_location_id
        choices = store.customer_choices()
        self.customer_map = {x["display_name"]: x["id"] for x in choices}
        keys = (
            "customer",
            "status",
            "priority",
            "received_date",
            "due_date",
            "assigned_to",
            "delivery_method",
            "po_number",
            "description",
            "artwork_path",
            "tax_rate",
            "deposit",
            "discount",
        )
        self.vars = {x: tk.StringVar() for x in keys}
        self.vars["status"].set("New")
        self.vars["priority"].set("Normal")
        self.vars["received_date"].set(date.today().isoformat())
        self.vars["delivery_method"].set("Pickup")
        self.vars["tax_rate"].set("0")
        self.vars["deposit"].set("0")
        self.vars["discount"].set("0")
        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True, padx=15, pady=(15, 6))
        details = ttk.Frame(tabs, padding=18)
        notes = ttk.Frame(tabs, padding=18)
        tabs.add(details, text="Order & Items")
        tabs.add(notes, text="Notes & Artwork")
        details.columnconfigure(1, weight=1)
        details.columnconfigure(3, weight=1)
        fields = [
            ("Customer *", "customer", 0, 0, self.customer_map.keys()),
            ("Status", "status", 0, 2, ORDER_STATUSES),
            ("Received date", "received_date", 2, 0, None),
            ("Due date", "due_date", 2, 2, None),
            ("Priority", "priority", 4, 0, PRIORITIES),
            ("Assigned to", "assigned_to", 4, 2, None),
            ("Delivery", "delivery_method", 6, 0, ("Pickup", "Local Delivery", "Ship")),
            ("Customer PO #", "po_number", 6, 2, None),
            ("Order title / description", "description", 8, 0, None),
        ]
        for label, key, row, col, values in fields:
            ttk.Label(details, text=label).grid(row=row, column=col, sticky="w", pady=(0, 2))
            widget = (
                ttk.Combobox(
                    details,
                    textvariable=self.vars[key],
                    values=list(values),
                    state="readonly",
                )
                if values
                else ttk.Entry(details, textvariable=self.vars[key])
            )
            span = 3 if key == "description" else 1
            widget.grid(
                row=row + 1,
                column=col,
                columnspan=span,
                sticky="ew",
                padx=(0, 16 if col == 0 else 0),
                pady=(0, 9),
            )
        ttk.Separator(details).grid(row=10, column=0, columnspan=4, sticky="ew", pady=6)
        ttk.Label(details, text="Line Items", font=("Segoe UI Semibold", 13)).grid(
            row=11, column=0, sticky="w"
        )
        ia = ttk.Frame(details)
        ia.grid(row=11, column=1, columnspan=3, sticky="e")
        ttk.Button(ia, text="+ Add", command=self.add_item).pack(side="left")
        ttk.Button(ia, text="Edit", command=self.edit_item).pack(side="left", padx=5)
        ttk.Button(ia, text="Remove", command=self.remove_item).pack(side="left")
        cols = ("item", "qty", "spec", "unit", "amount")
        self.item_tree = ttk.Treeview(details, columns=cols, show="headings", height=8)
        for c, t, w in zip(
            cols,
            ("Item", "Qty", "Specifications", "Unit Price", "Amount"),
            (180, 55, 340, 90, 95),
        ):
            self.item_tree.heading(c, text=t)
            self.item_tree.column(c, width=w, anchor="e" if c in ("qty", "unit", "amount") else "w")
        self.item_tree.grid(row=12, column=0, columnspan=4, sticky="nsew", pady=(7, 0))
        self.item_tree.bind("<Double-1>", lambda _e: self.edit_item())
        details.rowconfigure(12, weight=1)
        totals = ttk.Frame(details)
        totals.grid(row=13, column=1, columnspan=3, sticky="e", pady=10)
        for idx, (label, key, width) in enumerate(
            (
                ("Discount", "discount", 10),
                ("Tax %", "tax_rate", 8),
                ("Deposit", "deposit", 10),
            )
        ):
            ttk.Label(totals, text=label).grid(row=0, column=idx * 2, padx=(7, 3))
            ttk.Entry(totals, textvariable=self.vars[key], width=width).grid(
                row=0, column=idx * 2 + 1
            )
        self.total_label = ttk.Label(totals, text="Total: $0.00", font=("Segoe UI Semibold", 12))
        self.total_label.grid(row=1, column=0, columnspan=6, sticky="e", pady=(8, 0))
        for k in ("discount", "tax_rate", "deposit"):
            self.vars[k].trace_add("write", lambda *_: self.update_totals())
        notes.columnconfigure(0, weight=1)
        notes.rowconfigure(3, weight=1)
        notes.rowconfigure(5, weight=1)
        ttk.Label(notes, text="Artwork / source file path").grid(row=0, column=0, sticky="w")
        art = ttk.Frame(notes)
        art.grid(row=1, column=0, sticky="ew", pady=(3, 12))
        art.columnconfigure(0, weight=1)
        ttk.Entry(art, textvariable=self.vars["artwork_path"]).grid(row=0, column=0, sticky="ew")
        ttk.Button(art, text="Browse…", command=self.browse).grid(row=0, column=1, padx=5)
        ttk.Label(notes, text="Production notes (internal)").grid(row=2, column=0, sticky="w")
        self.production = tk.Text(notes, height=8, wrap="word", font=("Segoe UI", 10))
        self.production.grid(row=3, column=0, sticky="nsew", pady=(3, 10))
        ttk.Label(notes, text="Customer-facing notes").grid(row=4, column=0, sticky="w")
        self.customer_notes = tk.Text(notes, height=7, wrap="word", font=("Segoe UI", 10))
        self.customer_notes.grid(row=5, column=0, sticky="nsew", pady=(3, 0))
        foot = ttk.Frame(self, padding=(15, 4, 15, 13))
        foot.pack(fill="x")
        ttk.Button(foot, text="Cancel", command=self.destroy).pack(side="right", padx=5)
        ttk.Button(foot, text="Save Work Order", command=self.save, style="Primary.TButton").pack(
            side="right"
        )
        if order_id:
            self.load(order_id)
        elif customer_id:
            for n, cid in self.customer_map.items():
                if cid == customer_id:
                    self.vars["customer"].set(n)
                    break
        elif choices:
            self.vars["customer"].set(choices[0]["display_name"])

    def load(self, order_id):
        row = self.store.get_order(order_id)
        if not row:
            return
        for n, cid in self.customer_map.items():
            if cid == row["customer_id"]:
                self.vars["customer"].set(n)
                break
        for k in self.vars:
            if k != "customer" and k in row:
                self.vars[k].set("" if row[k] is None else str(row[k]))
        self.order_location_id = row["location_id"]
        self.production.insert("1.0", row["production_notes"])
        self.customer_notes.insert("1.0", row["customer_notes"])
        self.items = row["items"]
        self.refresh_items()

    def add_item(self):
        ItemDialog(self, on_saved=lambda x: (self.items.append(x), self.refresh_items()))

    def edit_item(self):
        sel = self.item_tree.selection()
        if not sel:
            messagebox.showinfo("Select an item", "Select a line item first.", parent=self)
            return
        i = int(sel[0])
        ItemDialog(self, self.items[i], lambda x: self.replace_item(i, x))

    def replace_item(self, i, item):
        self.items[i] = item
        self.refresh_items()

    def remove_item(self):
        sel = self.item_tree.selection()
        if sel:
            del self.items[int(sel[0])]
            self.refresh_items()

    def refresh_items(self):
        self.item_tree.delete(*self.item_tree.get_children())
        for i, x in enumerate(self.items):
            self.item_tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    x.get("item_name", ""),
                    f"{float(x.get('quantity', 0)):g}",
                    item_spec(x),
                    money(x.get("unit_price")),
                    money(float(x.get("quantity", 0)) * float(x.get("unit_price", 0))),
                ),
            )
        self.update_totals()

    def update_totals(self):
        try:
            vals = {k: float(self.vars[k].get() or 0) for k in ("discount", "tax_rate", "deposit")}
            tot = self.store.calculate_order(vals, self.items)
            self.total_label.configure(
                text=f"Subtotal: {money(tot['subtotal'])}   Total: {money(tot['total'])}   Balance: {money(tot['balance'])}"
            )
        except ValueError:
            self.total_label.configure(text="Check totals fields")

    def browse(self):
        p = filedialog.askopenfilename(parent=self)
        if p:
            self.vars["artwork_path"].set(p)

    def save(self):
        try:
            if self.vars["customer"].get() not in self.customer_map:
                raise ValueError("Select a customer.")
            if not self.items:
                raise ValueError("Add at least one line item.")
            values = {k: v.get().strip() for k, v in self.vars.items() if k != "customer"}
            values["customer_id"] = self.customer_map[self.vars["customer"].get()]
            values["location_id"] = self.order_location_id
            values["received_date"] = iso_date(values["received_date"], "Received date", False)
            values["due_date"] = iso_date(values["due_date"], "Due date")
            values["tax_rate"] = to_number(values["tax_rate"], "Tax rate")
            values["deposit"] = to_number(values["deposit"], "Deposit")
            values["discount"] = to_number(values["discount"], "Discount")
            values["production_notes"] = self.production.get("1.0", "end-1c").strip()
            values["customer_notes"] = self.customer_notes.get("1.0", "end-1c").strip()
            if min(values["tax_rate"], values["deposit"], values["discount"]) < 0:
                raise ValueError("Tax, deposit, and discount cannot be negative.")
            result = self.store.save_order(values, self.items, self.order_id)
            if self.on_saved:
                self.on_saved(result)
            self.destroy()
        except ValueError as exc:
            messagebox.showerror("Check work order", str(exc), parent=self)


class EmployeeDialog(tk.Toplevel):
    def __init__(self, parent, store, api, employee=None, on_saved=None):
        super().__init__(parent)
        self.store, self.api, self.employee, self.on_saved = (
            store,
            api,
            employee,
            on_saved,
        )
        self.title("Edit Employee" if employee else "Add Employee")
        self.geometry("540x500")
        self.transient(parent)
        self.grab_set()
        self.name = tk.StringVar(value=employee["name"] if employee else "")
        self.pin = tk.StringVar()
        self.role = tk.StringVar(value=employee["role"] if employee else "employee")
        self.active = tk.BooleanVar(value=bool(employee["active"]) if employee else True)
        self.locations = {f"{x['name']} #{x['store_number']}": x["id"] for x in store.locations()}
        self.location_vars = {
            k: tk.BooleanVar(value=(not employee or v in employee["location_ids"]))
            for k, v in self.locations.items()
        }
        f = ttk.Frame(self, padding=22)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="Employee Access", font=("Segoe UI Semibold", 18)).pack(
            anchor="w", pady=(0, 12)
        )
        for label, var, show in (
            ("Employee name", self.name, ""),
            ("New PIN" if employee else "PIN", self.pin, "•"),
        ):
            ttk.Label(f, text=label).pack(anchor="w", pady=(5, 2))
            ttk.Entry(f, textvariable=var, show=show).pack(fill="x")
        if employee:
            ttk.Label(f, text="Leave PIN blank to keep the current PIN.", foreground=MUTED).pack(
                anchor="w"
            )
        ttk.Label(f, text="Role").pack(anchor="w", pady=(9, 2))
        ttk.Combobox(
            f,
            textvariable=self.role,
            values=("employee", "supervisor", "admin"),
            state="readonly",
        ).pack(fill="x")
        ttk.Label(f, text="Assigned stores").pack(anchor="w", pady=(10, 2))
        for name, var in self.location_vars.items():
            ttk.Checkbutton(f, text=name, variable=var).pack(anchor="w")
        ttk.Checkbutton(f, text="Active", variable=self.active).pack(anchor="w", pady=8)
        b = ttk.Frame(f)
        b.pack(side="bottom", fill="x")
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right", padx=5)
        ttk.Button(b, text="Save", command=self.save, style="Primary.TButton").pack(side="right")

    def save(self):
        try:
            values = {
                "name": self.name.get().strip(),
                "role": self.role.get(),
                "location_ids": [
                    self.locations[k] for k, v in self.location_vars.items() if v.get()
                ],
            }
            if not values["name"]:
                raise ValueError("Employee name is required.")
            if self.pin.get():
                values["pin"] = self.pin.get()
            elif not self.employee:
                raise ValueError("A PIN of at least four characters is required.")
            if self.employee:
                values["active"] = self.active.get()
                result = self.api.update_employee(self.employee["id"], values)
            else:
                result = self.api.create_employee(values)
            self.on_saved(result)
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Unable to save", str(exc), parent=self)


if __name__ == "__main__":
    app = PrintOrderApp()
    if app.winfo_exists():
        app.mainloop()
