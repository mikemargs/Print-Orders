import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))

from app.storage.fake import FakeStorageAdapter


class StorageAdapterTests(unittest.TestCase):
    def test_fake_storage_authorize_verify_download_delete(self):
        storage = FakeStorageAdapter()
        auth = storage.create_upload_authorization('company/order/file/test.pdf', 'application/pdf', 10)
        self.assertNotIn('service', str(auth).lower())
        storage.mark_uploaded('company/order/file/test.pdf', b'0123456789', 'application/pdf')
        obj = storage.verify_uploaded_object('company/order/file/test.pdf', 10)
        self.assertEqual(obj.size_bytes, 10)
        self.assertTrue(storage.create_download_url('company/order/file/test.pdf', 60).startswith('https://fake-storage/'))
        storage.delete_object('company/order/file/test.pdf')
        with self.assertRaises(FileNotFoundError): storage.verify_uploaded_object('company/order/file/test.pdf', 10)


if __name__ == '__main__': unittest.main()

class StorageConfigurationTests(unittest.TestCase):
    def test_production_requires_explicit_non_fake_storage(self):
        import os
        from app.storage import get_storage, set_storage
        old_env = os.environ.get('APP_ENV')
        old_backend = os.environ.get('STORAGE_BACKEND')
        try:
            set_storage(None)
            os.environ['APP_ENV'] = 'production'
            os.environ.pop('STORAGE_BACKEND', None)
            with self.assertRaises(RuntimeError):
                get_storage()
            set_storage(None)
            os.environ['STORAGE_BACKEND'] = 'fake'
            with self.assertRaises(RuntimeError):
                get_storage()
        finally:
            set_storage(None)
            if old_env is None: os.environ.pop('APP_ENV', None)
            else: os.environ['APP_ENV'] = old_env
            if old_backend is None: os.environ.pop('STORAGE_BACKEND', None)
            else: os.environ['STORAGE_BACKEND'] = old_backend
