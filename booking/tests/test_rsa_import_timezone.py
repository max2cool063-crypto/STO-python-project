from unittest.mock import Mock, patch

from django.contrib import admin
from django.test import RequestFactory, TestCase

from booking.admin import StationAdmin
from booking.models import Station


class RsaImportTimezoneTests(TestCase):
    SEARCH_HTML = """
        <table>
          <tr class="table_row" data-request-id="request-1">
            <td><div class="status ok"></div></td>
            <td>RSA-TZ-001</td>
          </tr>
        </table>
    """
    DETAIL_HTML = """
        <div class="leftPanel">
          <div><h4>Полное наименование</h4><p> Самарская станция </p></div>
          <div><h4>Адрес</h4><p> Самара, тестовый адрес </p></div>
          <div><h4>Телефон</h4><p>+7 846 000-00-00</p></div>
          <div><h4>Email</h4><a>station@example.com</a></div>
        </div>
        <table class="popupTable">
          <tr><td>53.1959</td><td>50.1002</td></tr>
        </table>
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.station_admin = StationAdmin(Station, admin.site)

    @staticmethod
    def _response(html):
        response = Mock()
        response.text = html
        response.raise_for_status = Mock()
        return response

    def _run_import(self):
        request = self.factory.get(
            "/admin/booking/station/import-rsa-stream/",
            {"address": "Самара", "pages": "1"},
        )
        responses = [
            self._response(self.SEARCH_HTML),
            self._response(self.DETAIL_HTML),
        ]
        with patch("requests.get", side_effect=responses), patch(
            "booking.admin.time_mod.sleep"
        ):
            response = self.station_admin.import_rsa_stream(request)
            b"".join(response.streaming_content)

    def test_existing_station_with_empty_timezone_detects_it_on_refresh(self):
        station = Station.objects.create(
            name="Старое название",
            rsa_id="RSA-TZ-001",
            timezone="",
        )

        with patch(
            "booking.models.detect_timezone",
            return_value="Europe/Samara",
        ) as detect_timezone:
            self._run_import()

        station.refresh_from_db()
        detect_timezone.assert_called_once_with(53.1959, 50.1002)
        self.assertEqual(station.timezone, "Europe/Samara")
        self.assertEqual(station.latitude, 53.1959)
        self.assertEqual(station.longitude, 50.1002)
        self.assertEqual(station.name, "Самарская станция")
        self.assertEqual(station.address, "Самара, тестовый адрес")

    def test_existing_station_preserves_manually_set_timezone_on_refresh(self):
        station = Station.objects.create(
            name="Старое название",
            rsa_id="RSA-TZ-001",
            timezone="Asia/Yekaterinburg",
        )

        with patch("booking.models.detect_timezone") as detect_timezone:
            self._run_import()

        station.refresh_from_db()
        detect_timezone.assert_not_called()
        self.assertEqual(station.timezone, "Asia/Yekaterinburg")
        self.assertEqual(station.latitude, 53.1959)
        self.assertEqual(station.longitude, 50.1002)
