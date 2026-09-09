from datetime import time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from booking.models import Station, StationSchedule, StationStaff, StationWeeklySchedule


class StationScheduleValidationTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(
            username="schedule-validation-operator",
            password="Strong-operator-123!",
        )
        self.station = Station.objects.create(name="Schedule Validation Station")
        StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        self.client.login(
            username="schedule-validation-operator",
            password="Strong-operator-123!",
        )
        self.url = reverse("station_schedule", kwargs={"station_id": self.station.pk})

    def test_schedule_feedback_is_displayed_once(self):
        response = self.client.post(
            self.url,
            {"action": "save_weekly", "work_start_0": "09:00", "work_end_0": "17:00"},
            follow=True,
        )
        self.assertContains(response, "Недельное расписание сохранено", count=1)
        response = self.client.post(
            self.url,
            {"action": "save_weekly", "work_start_0": "17:00", "work_end_0": "09:00"},
            follow=True,
        )
        self.assertContains(
            response, "Проверьте недельный график: начало должно быть раньше окончания", count=1
        )

    def test_invalid_weekly_row_does_not_partially_mutate_other_days(self):
        monday = StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=0,
            work_start=time(9, 0),
            work_end=time(17, 0),
        )

        response = self.client.post(
            self.url,
            {
                "action": "save_weekly",
                "work_start_0": "08:00",
                "work_end_0": "18:00",
                "work_start_1": "18:00",
                "work_end_1": "09:00",
            },
        )

        self.assertRedirects(response, self.url)
        monday.refresh_from_db()
        self.assertEqual(monday.work_start, time(9, 0))
        self.assertEqual(monday.work_end, time(17, 0))
        self.assertFalse(
            StationWeeklySchedule.objects.filter(station=self.station, weekday=1).exists()
        )

    def test_reversed_exception_hours_are_rejected(self):
        response = self.client.post(
            self.url,
            {
                "action": "add_exception",
                "date": "2099-05-01",
                "work_start": "18:00",
                "work_end": "09:00",
            },
        )

        self.assertRedirects(response, self.url)
        self.assertFalse(
            StationSchedule.objects.filter(station=self.station, date="2099-05-01").exists()
        )

    def test_equal_exception_hours_remain_supported_as_day_off(self):
        response = self.client.post(
            self.url,
            {
                "action": "add_exception",
                "date": "2099-05-02",
                "work_start": "00:00",
                "work_end": "00:00",
            },
        )

        self.assertRedirects(response, self.url)
        exception = StationSchedule.objects.get(station=self.station, date="2099-05-02")
        self.assertEqual(exception.work_start, time(0, 0))
        self.assertEqual(exception.work_end, time(0, 0))

    def test_malformed_exception_date_is_rejected_without_server_error(self):
        response = self.client.post(
            self.url,
            {
                "action": "add_exception",
                "date": "not-a-date",
                "work_start": "09:00",
                "work_end": "18:00",
            },
        )

        self.assertRedirects(response, self.url)
        self.assertFalse(StationSchedule.objects.filter(station=self.station).exists())
