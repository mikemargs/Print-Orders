import sys
import unittest
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))

from app.storage.fake import FakeStorageAdapter
from app.storage.supabase import SupabaseStorageAdapter


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

    def test_modern_supabase_secret_key_uses_apikey_header_only(self):
        storage = SupabaseStorageAdapter(
            url='https://project.supabase.co',
            service_key='sb_secret_test-key',
            publishable_key='sb_publishable_test-key',
        )
        self.assertEqual(storage._headers, {'apikey': 'sb_secret_test-key'})

    def test_legacy_service_role_key_keeps_bearer_header(self):
        storage = SupabaseStorageAdapter(
            url='https://project.supabase.co',
            service_key='legacy-jwt-service-role-key',
            publishable_key='legacy-anon-key',
        )
        self.assertEqual(
            storage._headers,
            {
                'apikey': 'legacy-jwt-service-role-key',
                'Authorization': 'Bearer legacy-jwt-service-role-key',
            },
        )

    def test_supabase_error_body_is_included_in_runtime_error(self):
        request = httpx.Request('POST', 'https://project.supabase.co/storage/v1/object/upload/sign/bucket/file.png')
        response = httpx.Response(
            400,
            request=request,
            json={'statusCode': '400', 'error': 'Bad Request', 'message': 'sample storage failure'},
        )
        with self.assertRaisesRegex(RuntimeError, 'HTTP 400: sample storage failure'):
            SupabaseStorageAdapter._check_response(response, 'signed upload authorization')


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
