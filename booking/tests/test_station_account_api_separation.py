from datetime import date, time
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from booking.models import (
    Appointment,
    AppointmentPhoto,
    Brand,
    Car,
    CarModel,
    Station,
    StationStaff,
    StationWeeklySchedule,
)


class StationAccountApiSeparationTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(
            username="strict-api-operator",
            email="strict-api-operator@example.com",
            password="Strong-test-password-123!",
        )
        self.station = Station.objects.create(name="Operator station")
        self.foreign_station = Station.objects.create(name="Foreign station")
        StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
        )
        brand = Brand.objects.create(name="Strict API Brand")
        self.model = CarModel.objects.create(brand=brand, name="Strict API Model")
        self.car = Car.objects.create(
            owner=self.operator,
            model=self.model,
            plate_number="А111АА77",
        )
        self.client.force_login(self.operator)

    def _create_legacy_staff_appointment(self, station=None):
        station = station or self.station
        target = date(2099, 2, 3)
        StationWeeklySchedule.objects.create(
            station=station,
            weekday=target.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        start = station.make_local_datetime(target, time(10, 0))
        return Appointment.objects.create(
            station=station,
            user=self.operator,
            car=self.car,
            start=start,
            end=start,
            name="Legacy client identity",
        )

    def test_station_account_cannot_use_client_car_api(self):
        response = self.client.get(reverse("car_api", args=[self.car.pk]))

        self.assertEqual(response.status_code, 403)

    def test_station_account_cannot_use_client_slot_mode_for_foreign_station(self):
        response = self.client.get(
            reverse("station_slots_api", args=[self.foreign_station.pk]),
            {"date": "2099-02-03", "car": self.car.pk},
        )

        self.assertEqual(response.status_code, 403)

    def test_station_slot_lookup_does_not_treat_staff_owned_legacy_car_as_client(self):
        self._create_legacy_staff_appointment()

        response = self.client.get(
            reverse("station_slots_api", args=[self.station.pk]),
            {"date": "2099-02-03", "car": self.car.pk},
        )

        self.assertEqual(response.status_code, 404)

    def test_plate_lookup_hides_staff_owned_legacy_car(self):
        self._create_legacy_staff_appointment()

        response = self.client.get(
            reverse("car_by_plate_api"),
            {"station_id": self.station.pk, "plate": self.car.plate_number},
        )

        self.assertEqual(response.status_code, 404)

    def test_manual_client_booking_rejects_station_staff_email(self):
        target = date(2099, 2, 3)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=target.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        url = reverse(
            "station_appointment_create",
            kwargs={"station_id": self.station.pk},
        )

        response = self.client.post(
            url,
            {
                "plate": "В222ВВ77",
                "new_model_id": self.model.pk,
                "new_user_email": self.operator.email,
                "client_name": "Сотрудник как клиент",
                "client_phone": "",
                "start": "2099-02-03T11:00",
            },
        )

        self.assertRedirects(response, url)
        self.assertFalse(Appointment.objects.filter(station=self.station).exists())
        self.assertEqual(Car.objects.count(), 1)

    def test_station_account_does_not_gain_client_owner_media_access(self):
        appointment = self._create_legacy_staff_appointment(self.foreign_station)
        buffer = BytesIO()
        Image.new("RGB", (10, 10), "white").save(buffer, format="JPEG")
        photo = AppointmentPhoto.objects.create(
            appointment=appointment,
            image=SimpleUploadedFile(
                "strict-owner-access.jpg",
                buffer.getvalue(),
                content_type="image/jpeg",
            ),
        )

        response = self.client.get(
            reverse("protected_media", kwargs={"path": photo.image.name})
        )

        self.assertEqual(response.status_code, 404)
