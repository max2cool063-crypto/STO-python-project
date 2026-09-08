from django.conf import settings
from django.test import SimpleTestCase, override_settings
from whitenoise.storage import CompressedManifestStaticFilesStorage

from auto_booking.storage import JazzminCompatibleCompressedManifestStaticFilesStorage


class StaticStorageConfigurationTests(SimpleTestCase):
    def test_staticfiles_uses_jazzmin_compatible_whitenoise_manifest_backend(self):
        self.assertEqual(
            settings.STORAGES["staticfiles"]["BACKEND"],
            "auto_booking.storage.JazzminCompatibleCompressedManifestStaticFilesStorage",
        )
        self.assertTrue(
            issubclass(
                JazzminCompatibleCompressedManifestStaticFilesStorage,
                CompressedManifestStaticFilesStorage,
            )
        )

    @override_settings(DEBUG=False)
    def test_jazzmin_bootswatch_directory_base_is_allowed(self):
        storage = JazzminCompatibleCompressedManifestStaticFilesStorage()

        self.assertEqual(
            storage.url("vendor/bootswatch"),
            "/static/vendor/bootswatch",
        )

    @override_settings(DEBUG=False)
    def test_manifest_remains_strict_for_other_missing_assets(self):
        storage = JazzminCompatibleCompressedManifestStaticFilesStorage()

        with self.assertRaisesMessage(ValueError, "Missing staticfiles manifest entry"):
            storage.url("definitely-missing-static-asset.css")
