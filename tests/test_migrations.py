import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / 'server'


class MigrationTests(unittest.TestCase):
    def test_alembic_upgrade_creates_current_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / 'migration.db'
            env = dict(os.environ, DATABASE_URL=f'sqlite:///{db_path}')
            result = subprocess.run(
                [sys.executable, '-m', 'alembic', '-c', str(SERVER / 'alembic.ini'), 'upgrade', 'head'],
                cwd=SERVER,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with closing(sqlite3.connect(db_path)) as conn:
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({'companies','locations','employees','customers','work_orders','sync_events','processed_operations','artwork_files'}.issubset(tables), tables)

    def test_bootstrap_upgrades_unversioned_existing_database(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "legacy.db"
            env = dict(os.environ, DATABASE_URL=f"sqlite:///{db_path}")
            first = subprocess.run([sys.executable, "-m", "alembic", "-c", str(SERVER / "alembic.ini"), "upgrade", "0001_baseline"], cwd=SERVER, env=env, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("DROP TABLE alembic_version")
                conn.commit()
            upgraded = subprocess.run([sys.executable, str(SERVER / "migrate_database.py")], cwd=SERVER, env=env, capture_output=True, text=True)
            self.assertEqual(upgraded.returncode, 0, upgraded.stdout + upgraded.stderr)
            with closing(sqlite3.connect(db_path)) as conn:
                employee_cols = {row[1] for row in conn.execute("PRAGMA table_info(employees)")}
                processed_cols = {row[1] for row in conn.execute("PRAGMA table_info(processed_operations)")}
            self.assertIn("auth_version", employee_cols)
            self.assertIn("operation_id", processed_cols)
            self.assertIn("row_id", processed_cols)
            with closing(sqlite3.connect(db_path)) as conn:
                artwork_cols = {row[1] for row in conn.execute("PRAGMA table_info(artwork_files)")}
            self.assertTrue({"size_bytes","active","deleted","object_key"}.issubset(artwork_cols))

    def test_bootstrap_refuses_to_guess_when_unversioned_schema_is_not_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "ambiguous.db"
            env = dict(os.environ, DATABASE_URL=f"sqlite:///{db_path}")
            first = subprocess.run(
                [sys.executable, "-m", "alembic", "-c", str(SERVER / "alembic.ini"), "upgrade", "head"],
                cwd=SERVER,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("DROP TABLE alembic_version")
                conn.commit()
            upgraded = subprocess.run(
                [sys.executable, str(SERVER / "migrate_database.py")],
                cwd=SERVER,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(upgraded.returncode, 0)
            self.assertIn("cannot safely infer", (upgraded.stdout + upgraded.stderr).lower())

    def test_production_startup_does_not_create_schema(self):
        main_source = (SERVER / 'app' / 'main.py').read_text(encoding='utf-8')
        self.assertNotIn('Base.metadata.create_all(engine)', main_source)


if __name__ == '__main__':
    unittest.main()
