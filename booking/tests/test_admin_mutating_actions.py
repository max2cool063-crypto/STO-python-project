from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.http import HttpResponse
from django.test import Client, TestCase
from django.urls import reverse

from booking.admin import StationAdmin
from booking.models import Station, StationSchedule


class AdminMutatingActionsTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="Admin-password-123!",
            is_staff=True,
            is_superuser=True,
        )
        self.station = Station.objects.create(name="Test station", address="Test address")
        self.client.force_login(self.admin_user)

    def test_fill_holidays_get_does_not_mutate(self):
        url = reverse("station_fill_holidays", args=[self.station.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(StationSchedule.objects.filter(station=self.station).count(), 0)
        self.assertContains(response, "Заполнить праздники")

    @patch("holidays.Russia")
    def test_fill_holidays_post_mutates(self, russia_holidays):
        holiday = date(date.today().year, 1, 1)
        russia_holidays.return_value = {holiday: "Test holiday"}
        url = reverse("station_fill_holidays", args=[self.station.pk])

        response = self.client.post(url)

        self.assertRedirects(response, reverse("admin:booking_station_change", args=[self.station.pk]))
        self.assertTrue(
            StationSchedule.objects.filter(station=self.station, date=holiday).exists()
        )

    def test_fill_holidays_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin_user)
        url = reverse("station_fill_holidays", args=[self.station.pk])

        response = client.post(url)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(StationSchedule.objects.filter(station=self.station).count(), 0)

    def test_rsa_import_get_is_not_allowed(self):
        url = reverse("station_import_rsa_stream")

        response = self.client.get(url, {"address": "Москва", "pages": 1})

        self.assertEqual(response.status_code, 405)

    def test_rsa_import_post_validates_pages(self):
        url = reverse("station_import_rsa_stream")

        response = self.client.post(url, {"address": "Москва", "pages": "129"})

        self.assertEqual(response.status_code, 400)

    def test_rsa_import_post_delegates_to_importer(self):
        url = reverse("station_import_rsa_stream")
        with patch.object(StationAdmin, "import_rsa_stream", return_value=HttpResponse("ok")) as importer:
            response = self.client.post(url, {"address": "Москва", "pages": "1"})

        self.assertEqual(response.status_code, 200)
        importer.assert_called_once()
        request = importer.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.POST["address"], "Москва")
        self.assertEqual(request.GET["address"], "Москва")

    def test_rsa_import_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin_user)
        url = reverse("station_import_rsa_stream")

        response = client.post(url, {"address": "Москва", "pages": "1"})

        self.assertEqual(response.status_code, 403)

    def _create_staff_without_station_change_permission(self):
        user = User.objects.create_user(
            username="limited-admin@example.com",
            password="Admin-password-123!",
            is_staff=True,
        )
        user.user_permissions.add(
            Permission.objects.get(codename="view_station", content_type__app_label="booking")
        )
        return user

    def test_fill_holidays_requires_station_change_permission(self):
        user = self._create_staff_without_station_change_permission()
        client = Client()
        client.force_login(user)
        url = reverse("station_fill_holidays", args=[self.station.pk])

        response = client.get(url)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(StationSchedule.objects.filter(station=self.station).count(), 0)

    def test_rsa_import_requires_station_change_permission(self):
        user = self._create_staff_without_station_change_permission()
        client = Client()
        client.force_login(user)
        url = reverse("station_import_rsa_stream")

        response = client.post(url, {"address": "Москва", "pages": "1"})

        self.assertEqual(response.status_code, 403)
