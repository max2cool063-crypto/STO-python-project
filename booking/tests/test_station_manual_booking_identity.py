from datetime import date, datetime, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import Appointment, Brand, CarModel, Station, StationStaff, StationWeeklySchedule


class StationManualBookingIdentityTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(
            username="manual-identity-operator",
            password="Strong-operator-123!",
        )
        self.station = Station.objects.create(name="Manual Identity Station")
        StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        brand = Brand.objects.create(name="Manual Identity Brand")
        self.model = CarModel.objects.create(
            brand=brand,
            name="Manual Identity Model",
            vehicle_type="CAR",
        )
        target = date(2099, 4, 7)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=target.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        self.start = "2099-04-07T10:00:00+03:00"
        self.client.login(
            username="manual-identity-operator",
            password="Strong-operator-123!",
        )
        self.url = reverse(
            "station_appointment_create",
            kwargs={"station_id": self.station.pk},
        )

    def test_manual_booking_rejects_malformed_optional_email(self):
        response = self.client.post(
            self.url,
            {
                "plate": "А111АА77",
                "new_model_id": self.model.pk,
                "new_user_email": "not-an-email",
                "client_name": "Новый Клиент",
                "client_phone": "+79990001122",
                "start": self.start,
            },
        )

        self.assertRedirects(response, self.url)
        self.assertFalse(Appointment.objects.filter(station=self.station).exists())
        self.assertFalse(User.objects.filter(email="not-an-email").exists())

    def test_existing_client_email_does_not_allow_global_profile_overwrite(self):
        existing = User.objects.create_user(
            username="existing-global-client",
            email="global-client@example.com",
            first_name="Иван",
            last_name="Иванов",
        )
        existing.profile.phone = "+79991112233"
        existing.profile.save(update_fields=["phone"])

        response = self.client.post(
            self.url,
            {
                "plate": "В222ВВ77",
                "new_model_id": self.model.pk,
                "new_user_email": "GLOBAL-CLIENT@example.com",
                "client_name": "Подменённое Имя",
                "client_phone": "+79998887766",
                "start": self.start,
            },
        )

        self.assertRedirects(
            response,
            reverse("station_appointments", kwargs={"station_id": self.station.pk}),
        )
        existing.refresh_from_db()
        existing.profile.refresh_from_db()
        appointment = Appointment.objects.get(station=self.station)
        self.assertEqual(existing.first_name, "Иван")
        self.assertEqual(existing.last_name, "Иванов")
        self.assertEqual(existing.profile.phone, "+79991112233")
        self.assertEqual(appointment.user_id, existing.pk)
        self.assertEqual(appointment.name, "Иванов Иван")
        self.assertEqual(appointment.phone, "+79991112233")
