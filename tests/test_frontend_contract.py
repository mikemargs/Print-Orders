import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FrontendOfflineSessionContractTests(unittest.TestCase):
    def test_cached_session_retains_non_secret_csrf_for_deferred_logout(self):
        source = (ROOT / 'web/src/offline/db.ts').read_text(encoding='utf-8')
        self.assertIn("JSON.stringify(session)", source)
        self.assertNotIn("const { csrf_token: _csrf, ...safe } = session", source)

    def test_main_and_store_dashboards_keep_distinct_scopes(self):
        main = (ROOT / 'web/src/features/dashboard/DashboardPage.tsx').read_text(encoding='utf-8')
        store = (ROOT / 'web/src/features/dashboard/StoreDashboardPage.tsx').read_text(encoding='utf-8')
        self.assertIn("/api/orders?limit=${PAGE_SIZE}&offset=${offset}", main)
        self.assertNotIn("location_id=${encodeURIComponent(locationId)}", main)
        self.assertIn("location_id=${encodeURIComponent(locationId)}", store)
        self.assertIn("order.location_id === locationId", store)

    def test_non_admin_order_editor_only_offers_selected_store(self):
        source = (ROOT / 'web/src/features/orders/OrderEditor.tsx').read_text(encoding='utf-8')
        self.assertIn("session?.employee.role==='admin'?session.locations", source)
        self.assertIn("[session?.location].filter(Boolean)", source)

    def test_delete_controls_match_backend_roles(self):
        customer = (ROOT / 'web/src/features/customers/CustomerEditor.tsx').read_text(encoding='utf-8')
        order = (ROOT / 'web/src/features/orders/OrderEditor.tsx').read_text(encoding='utf-8')
        self.assertIn("session?.employee.role==='supervisor'||session?.employee.role==='admin'", customer)
        self.assertIn("method:'DELETE'", customer)
        self.assertIn("session?.employee.role==='supervisor'||session?.employee.role==='admin'", order)
        self.assertIn("Delete work order", order)
        self.assertIn("method:'DELETE'", order)

    def test_offline_refresh_restores_csrf_and_pending_logout_blocks_session_restore(self):
        source = (ROOT / 'web/src/auth/SessionContext.tsx').read_text(encoding='utf-8')
        self.assertIn("setCsrfToken(cached.csrf_token)", source)
        self.assertIn("if (!navigator.onLine) return true", source)
        self.assertIn("getCsrfToken()", source)
        self.assertIn("setPendingLogoutCsrf(csrf)", source)


if __name__ == '__main__':
    unittest.main()
