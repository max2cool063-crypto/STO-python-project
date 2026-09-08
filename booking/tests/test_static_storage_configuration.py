from django.conf import settings
from django.test import SimpleTestCase


class StaticStorageConfigurationTests(SimpleTestCase):
    def test_staticfiles_uses_whitenoise_manifest_backend(self):
        self.assertEqual(
            settings.STORAGES["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )
