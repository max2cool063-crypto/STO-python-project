from pathlib import Path

from django.test import SimpleTestCase


class UiDesignSystemTests(SimpleTestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        self.base_template = (self.root / "templates" / "base.html").read_text(encoding="utf-8")
        self.station_base_template = (
            self.root / "templates" / "booking" / "station" / "base.html"
        ).read_text(encoding="utf-8")

    def test_shared_ui_assets_exist(self):
        self.assertTrue(
            (self.root / "booking" / "static" / "booking" / "css" / "ui-design-system-v1.css").is_file()
        )
        self.assertTrue(
            (self.root / "booking" / "static" / "booking" / "js" / "ui-icons-v1.js").is_file()
        )

    def test_base_template_loads_lucide_and_design_system(self):
        self.assertIn("booking/css/ui-design-system-v1.css", self.base_template)
        self.assertIn("lucide@1.33.0/dist/umd/lucide.js", self.base_template)
        self.assertIn("booking/js/ui-icons-v1.js", self.base_template)
        self.assertIn('data-lucide="log-out"', self.base_template)

    def test_station_navigation_uses_lucide_icons(self):
        for icon_name in (
            "layout-dashboard",
            "calendar-days",
            "clipboard-list",
            "clock-3",
            "ban",
            "users",
            "user-round-cog",
            "arrow-left",
        ):
            self.assertIn(f'data-lucide="{icon_name}"', self.station_base_template)
