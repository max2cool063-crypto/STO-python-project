from datetime import date, datetime, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import Appointment, Brand, Car, CarModel, Station, StationStaff, StationWeeklySchedule


class StationAppointmentEditIdentityTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(username="edit-operator", password="test-password")
        self.station = Station.objects.create(name="Edit Test Station")
        StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        self.brand = Brand.objects.create(name="Edit Brand")
        self.model = CarModel.objects.create(brand=self.brand, name="Edit Model", vehicle_type="CAR")
        target = date(2099, 3, 4)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=target.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        self.user = User.objects.create_user(
            username="original-client",
            first_name="Иван",
            last_name="Иванов",
        )
        self.car = Car.objects.create(
            owner=self.user,
            model=self.model,
            plate_number="А123АА63",
        )
        self.start = timezone.make_aware(datetime(2099, 3, 4, 10, 0))
        self.appointment = Appointment.objects.create(
            station=self.station,
            user=self.user,
            car=self.car,
            start=self.start,
            end=self.start,
            name="Иванов Иван",
            phone="+79123456789",
        )
        self.client.login(username="edit-operator", password="test-password")

    def test_edit_form_locks_client_identity_fields(self):
        response = self.client.get(
            reverse("station_appointment_edit", kwargs={"station_id": self.station.pk, "pk": self.appointment.pk})
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('name="client_name"', content)
        self.assertIn('name="client_phone"', content)
        self.assertIn('readonly', content)

    def test_post_cannot_change_client_name_or_phone(self):
        response = self.client.post(
            reverse("station_appointment_edit", kwargs={"station_id": self.station.pk, "pk": self.appointment.pk}),
            {
                "client_name": "Другой Клиент",
                "client_phone": "+79999999999",
                "start": "2099-03-04T10:00",
                "notes": "Новый комментарий",
            },
        )
        self.assertRedirects(
            response,
            reverse("station_appointment_detail", kwargs={"station_id": self.station.pk, "pk": self.appointment.pk}),
        )
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.name, "Иванов Иван")
        self.assertEqual(self.appointment.phone, "+79123456789")
        self.assertEqual(self.appointment.notes, "Новый комментарий")
