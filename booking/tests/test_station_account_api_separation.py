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
        model = CarModel.objects.create(brand=brand, name="Strict API Model")
        self.car = Car.objects.create(
            owner=self.operator,
            model=model,
            plate_number="А111АА77",
        )
        self.client.force_login(self.operator)

    def test_station_account_cannot_use_client_car_api(self):
        response = self.client.get(reverse("car_api", args=[self.car.pk]))

        self.assertEqual(response.status_code, 403)

    def test_station_account_cannot_use_client_slot_mode_for_foreign_station(self):
        response = self.client.get(
            reverse("station_slots_api", args=[self.foreign_station.pk]),
            {"date": "2099-02-03", "car": self.car.pk},
        )

        self.assertEqual(response.status_code, 403)

    def test_station_account_does_not_gain_client_owner_media_access(self):
        target = date(2099, 2, 3)
        StationWeeklySchedule.objects.create(
            station=self.foreign_station,
            weekday=target.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        start = self.foreign_station.make_local_datetime(target, time(10, 0))
        appointment = Appointment.objects.create(
            station=self.foreign_station,
            user=self.operator,
            car=self.car,
            start=start,
            end=start,
            name="Legacy client identity",
        )
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
