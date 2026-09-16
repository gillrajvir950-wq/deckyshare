import ssl
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import updater


class UpdaterTLSTests(unittest.TestCase):
    def test_system_ca_candidates_are_first(self):
        first = next(iter(updater._candidate_ca_bundles()))
        self.assertEqual(first, "/etc/ssl/certs/ca-certificates.crt")

    def test_existing_ca_file_is_passed_to_verified_context(self):
        with tempfile.NamedTemporaryFile() as ca:
            sentinel = object()
            with mock.patch.object(updater, "_candidate_ca_bundles", return_value=iter([ca.name])):
                with mock.patch.object(updater.ssl, "create_default_context", return_value=sentinel) as create:
                    self.assertIs(updater._ssl_context(), sentinel)
                    create.assert_called_once_with(cafile=ca.name)

    def test_real_context_keeps_verification_enabled(self):
        context = updater._ssl_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)


if __name__ == "__main__":
    unittest.main()
