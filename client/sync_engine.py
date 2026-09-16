from __future__ import annotations

import threading
from collections.abc import Callable

from api_client import ApiClient, ApiError
from local_store import LocalStore


def sync_once(store: LocalStore, api: ApiClient) -> dict:
    if not api.employee_token:
        raise ApiError("Employee sign-in is required before synchronization")
    # Refresh store and employee permissions so changes made by an administrator
    # propagate without requiring every workstation to restart.
    store.cache_bootstrap(api.bootstrap())
    pushed = 0
    operations = store.pending_operations(100)
    if operations:
        response = api.push(operations)
        store.apply_push_results(response.get("results", []))
        pushed = len(response.get("results", []))
    cursor = int(store.get_meta("sync_cursor", "0"))
    pulled = 0
    while True:
        response = api.pull(cursor)
        events = response.get("events", [])
        cursor = int(response.get("cursor", cursor))
        store.apply_events(events, cursor)
        pulled += len(events)
        if not response.get("has_more"):
            break
    return {
        "pushed": pushed,
        "pulled": pulled,
        "pending": store.pending_count(),
        "conflicts": store.conflict_count(),
    }


class SyncWorker:
    def __init__(
        self,
        store: LocalStore,
        api: ApiClient,
        callback: Callable[[str, dict], None],
        interval: int = 20,
    ):
        self.store, self.api, self.callback, self.interval = (
            store,
            api,
            callback,
            interval,
        )
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="print-order-sync")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def trigger(self) -> None:
        self._wake.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                result = sync_once(self.store, self.api)
                self.callback("online", result)
            except Exception as exc:
                self.callback(
                    "offline",
                    {
                        "message": str(exc),
                        "pending": self.store.pending_count(),
                        "conflicts": self.store.conflict_count(),
                    },
                )
            self._wake.wait(self.interval)
            self._wake.clear()
