from datetime import datetime, time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.validators import validate_email
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import Appointment, Brand, Car, CarModel, Station, StationSchedule, StationStaff


class InputBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="boundary-client")
        cls.owner = User.objects.create_user(username="boundary-owner")
        cls.station = Station.objects.create(name="Boundary station")
        StationStaff.objects.create(station=cls.station, user=cls.owner, role=StationStaff.ROLE_OWNER)
        brand = Brand.objects.create(name="Boundary brand")
        model = CarModel.objects.create(brand=brand, name="Car", vehicle_type="CAR")
        cls.car = Car.objects.create(owner=cls.user, model=model, plate_number="А111АА77")
        start = timezone.make_aware(datetime(2099, 3, 3, 10))
        StationSchedule.objects.create(station=cls.station, date=start.date(), work_start=time(9), work_end=time(18))
        cls.appointment = Appointment.objects.create(station=cls.station, user=cls.user, car=cls.car, start=start, end=start, name="Client")

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_long_registration_email_is_rejected_without_creating_user(self):
        email = "a" * 64 + "@" + "b" * 60 + "." + "c" * 30 + ".com"
        validate_email(email)
        with patch("booking.views.auth.send_mail") as send:
            response = self.client.post(reverse("register"), {"email": email})
        self.assertRedirects(response, reverse("register"))
        self.assertFalse(User.objects.filter(email=email).exists())
        send.assert_not_called()

    def test_existing_client_with_long_email_can_still_request_password_link(self):
        email = "a" * 64 + "@" + "b" * 60 + "." + "c" * 30 + ".com"
        User.objects.create_user(username="short-existing-login", email=email)
        with patch("booking.views.auth.send_mail") as send:
            response = self.client.post(reverse("register"), {"email": email})
        self.assertRedirects(response, reverse("login"))
        send.assert_called_once()

    def test_valid_email_local_part_is_not_restricted_by_username_regex(self):
        email = "o'connor@example.com"
        with patch("booking.views.auth.send_mail"):
            response = self.client.post(reverse("register"), {"email": email})
        self.assertRedirects(response, reverse("login"))
        self.assertTrue(User.objects.filter(username=email, email=email).exists())

    def test_missing_and_impossible_booking_dates_do_not_raise(self):
        self.client.force_login(self.user)
        url = reverse("book_station", kwargs={"pk": self.station.pk})
        for value in (None, "", "garbage", "2099-02-30T10:00", "2099-03-03T25:00"):
            with self.subTest(value=value):
                payload = {"car": self.car.pk}
                if value is not None:
                    payload["start"] = value
                self.assertRedirects(self.client.post(url, payload), url)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_impossible_station_dates_do_not_mutate(self):
        self.client.force_login(self.owner)
        cases = [
            ("station_appointment_create", {"station_id": self.station.pk}, {"start": "2099-02-30T10:00", "client_name": "Client"}),
            ("station_appointment_edit", {"station_id": self.station.pk, "pk": self.appointment.pk}, {"start": "2099-02-30T10:00"}),
            ("station_slot_blocks", {"station_id": self.station.pk}, {"action": "add", "start": "2099-02-30T10:00", "end": "2099-03-03T11:00"}),
            ("station_schedule", {"station_id": self.station.pk}, {"action": "add_exception", "date": "2099-02-30", "work_start": "09:00", "work_end": "18:00"}),
            ("station_schedule", {"station_id": self.station.pk}, {"action": "add_exception", "date": "2099-03-03", "work_start": "25:00", "work_end": "18:00"}),
        ]
        for name, kwargs, payload in cases:
            with self.subTest(name=name, payload=payload):
                url = reverse(name, kwargs=kwargs)
                self.assertRedirects(self.client.post(url, payload), url)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.local_start.hour, 10)
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertFalse(self.station.slot_blocks.exists())
        self.assertEqual(StationSchedule.objects.count(), 1)

    def test_slots_api_returns_no_slots_for_impossible_date(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("station_slots_api", kwargs={"station_id": self.station.pk}), {"date": "2099-02-30"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slots"], [])

    def test_operator_fields_are_validated_before_database_write(self):
        self.client.force_login(self.owner)
        url = reverse("station_staff_create_operator", kwargs={"station_id": self.station.pk})
        original_count = User.objects.count()
        for field in ("login", "first_name", "last_name"):
            with self.subTest(field=field), patch("booking.views.station_staff_manage.send_mail") as send:
                payload = {"login": "new-operator", "password": "Strong-operator-123!", field: "x" * 151}
                response = self.client.post(url, payload)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(User.objects.count(), original_count)
                send.assert_not_called()

    def test_invalid_staff_profile_does_not_partially_save(self):
        self.client.force_login(self.owner)
        member = self.owner.station_roles.get()
        url = reverse("station_staff_edit_profile", kwargs={"station_id": self.station.pk, "member_id": member.pk})
        response = self.client.post(url, {"first_name": "x" * 151, "email": "changed@example.com", "phone": "+79990002233"})
        self.assertRedirects(response, url)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.email, "")
        self.assertEqual(self.owner.first_name, "")

    def test_operator_is_created_but_failed_welcome_email_is_logged(self):
        self.client.force_login(self.owner)
        url = reverse("station_staff_create_operator", kwargs={"station_id": self.station.pk})
        response = self.client.post(url, {"login": "welcome-failure", "email": "operator@example.com", "password": "Strong-operator-123!"})
        from booking.email_queue import process_one
        with patch("booking.email_queue.EmailMessage.send", side_effect=ConnectionError("unavailable")), self.assertLogs("booking.email_queue", level="ERROR"):
            process_one()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(StationStaff.objects.filter(user__username="welcome-failure", station=self.station).exists())
