from django.test import SimpleTestCase, override_settings
from django.urls import reverse


@override_settings(STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class PwaTests(SimpleTestCase):
    def test_manifest_has_installable_icons_and_scope(self):
        response = self.client.get(reverse("pwa_manifest"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        manifest = response.json()
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual({icon["sizes"] for icon in manifest["icons"]}, {"192x192", "512x512"})

    def test_worker_is_public_javascript_at_root(self):
        response = self.client.get(reverse("pwa_service_worker"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/javascript")
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertNotIn("sessionid", response.cookies)

    def test_offline_page_needs_no_scripts_or_remote_assets(self):
        response = self.client.get(reverse("pwa_offline"))
        self.assertContains(response, "Нет соединения")
        self.assertNotContains(response, "<script")
        self.assertNotContains(response, "https://")
        self.assertNotIn("sessionid", response.cookies)

    def test_resources_do_not_accept_form_submissions(self):
        for name in ("pwa_manifest", "pwa_service_worker", "pwa_offline"):
            self.assertEqual(self.client.post(reverse(name)).status_code, 405)
