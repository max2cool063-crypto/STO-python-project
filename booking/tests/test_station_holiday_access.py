from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from booking.models import Station, StationSchedule, StationStaff


class StationHolidayAccessTests(TestCase):
    def setUp(self):
        self.station = Station.objects.create(name="Station A")
        self.other_station = Station.objects.create(name="Station B")

        self.operator = User.objects.create_user(
            username="operator@example.com",
            password="test-password",
        )
        self.owner = User.objects.create_user(
            username="owner@example.com",
            password="test-password",
        )

        StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        StationStaff.objects.create(
            station=self.station,
            user=self.owner,
            role=StationStaff.ROLE_OWNER,
            is_active=True,
        )

    def holiday_url(self, station):
        return reverse("station_schedule", kwargs={"station_id": station.id})

    def test_operator_can_fill_holidays_for_own_station(self):
        self.client.login(username="operator@example.com", password="test-password")

        response = self.client.post(
            self.holiday_url(self.station),
            {"action": "fill_holidays", "year": "2027"},
        )

        self.assertRedirects(response, self.holiday_url(self.station))
        self.assertGreater(
            StationSchedule.objects.filter(station=self.station, date__year=2027).count(),
            0,
        )
        self.assertEqual(
            StationSchedule.objects.filter(station=self.other_station, date__year=2027).count(),
            0,
        )

    def test_operator_cannot_fill_holidays_for_foreign_station(self):
        self.client.login(username="operator@example.com", password="test-password")

        response = self.client.post(
            self.holiday_url(self.other_station),
            {"action": "fill_holidays", "year": "2027"},
        )

        self.assertRedirects(
            response,
            reverse("station_select"),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            StationSchedule.objects.filter(station=self.other_station, date__year=2027).count(),
            0,
        )

    def test_owner_can_fill_holidays_for_own_station(self):
        self.client.login(username="owner@example.com", password="test-password")

        response = self.client.post(
            self.holiday_url(self.station),
            {"action": "fill_holidays", "year": "2027"},
        )

        self.assertRedirects(response, self.holiday_url(self.station))
        self.assertGreater(
            StationSchedule.objects.filter(station=self.station, date__year=2027).count(),
            0,
        )

    def test_get_does_not_fill_holidays(self):
        self.client.login(username="operator@example.com", password="test-password")

        response = self.client.get(self.holiday_url(self.station))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            StationSchedule.objects.filter(station=self.station, date=date(2027, 1, 1)).exists()
        )
