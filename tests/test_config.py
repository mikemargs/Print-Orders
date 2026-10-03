import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'client'))

import config
import credential_store


class ConfigTests(unittest.TestCase):
    def test_legacy_plaintext_company_token_is_migrated_and_scrubbed(self):
        with tempfile.TemporaryDirectory() as folder:
            json_path = Path(folder) / 'client_config.json'
            token_path = Path(folder) / 'company_token.dev'
            json_path.write_text('{"server_url": "https://example.test", "company_token": "legacy-secret-token"}', encoding='utf-8')
            with patch('config.config_path', return_value=json_path), patch('credential_store._fallback_path', return_value=token_path), patch('credential_store.os.name', 'posix'):
                loaded = config.load_config()
                self.assertEqual(loaded['company_token'], 'legacy-secret-token')
                self.assertEqual(token_path.read_text(encoding='utf-8'), 'legacy-secret-token')
                self.assertNotIn('legacy-secret-token', json_path.read_text(encoding='utf-8'))
                self.assertNotIn('company_token', json_path.read_text(encoding='utf-8'))

    def test_company_token_is_not_written_to_json(self):
        with tempfile.TemporaryDirectory() as folder:
            json_path = Path(folder) / 'client_config.json'
            token_path = Path(folder) / 'company_token.dev'
            with patch('config.config_path', return_value=json_path), patch('credential_store._fallback_path', return_value=token_path), patch('credential_store.os.name', 'posix'):
                config.save_config({'server_url': 'https://example.test', 'company_token': 'super-secret-token'})
                self.assertNotIn('super-secret-token', json_path.read_text(encoding='utf-8'))
                loaded = config.load_config()
                self.assertEqual(loaded['company_token'], 'super-secret-token')
                credential_store.delete_company_token()
                self.assertEqual(credential_store.load_company_token(), '')


if __name__ == '__main__':
    unittest.main()
