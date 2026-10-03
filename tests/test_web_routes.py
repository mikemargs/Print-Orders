import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("JWT_SECRET", "route-test-secret-that-is-longer-than-thirty-two")
sys.path.insert(0, str(ROOT / "server"))

from app.main import app
from fastapi.testclient import TestClient


class WebRouteTests(unittest.TestCase):
    def test_unknown_api_never_falls_through_to_spa(self):
        client = TestClient(app)
        response = client.get("/api/definitely-not-a-route")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("<div id=\"root\">", response.text)

    def test_browser_deep_link_serves_spa_index(self):
        with tempfile.TemporaryDirectory() as folder:
            dist = Path(folder)
            (dist / "index.html").write_text('<html><body><div id="root">SPA</div></body></html>', encoding="utf-8")
            old = os.environ.get("WEB_DIST_DIR")
            os.environ["WEB_DIST_DIR"] = str(dist)
            try:
                client = TestClient(app)
                response = client.get("/orders/abc")
            finally:
                if old is None:
                    os.environ.pop("WEB_DIST_DIR", None)
                else:
                    os.environ["WEB_DIST_DIR"] = old
            self.assertEqual(response.status_code, 200)
            self.assertIn('<div id="root">SPA</div>', response.text)


if __name__ == "__main__":
    unittest.main()
