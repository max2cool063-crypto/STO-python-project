from datetime import date, time
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from booking.models import Appointment, AppointmentPhoto, Brand, Car, CarModel, Station, StationStaff, StationWeeklySchedule


class StationStaffMediaAccessTests(TestCase):
    def test_active_station_operator_can_open_appointment_photo(self):
        operator = User.objects.create_user(username="media-operator", password="test-password")
        client_user = User.objects.create_user(username="media-client", password="test-password")
        station = Station.objects.create(name="Media Station")
        StationStaff.objects.create(station=station, user=operator, role=StationStaff.ROLE_OPERATOR, is_active=True)
        brand = Brand.objects.create(name="Media Brand")
        model = CarModel.objects.create(brand=brand, name="Media Model", vehicle_type="CAR")
        car = Car.objects.create(owner=client_user, model=model, plate_number="M111MM")
        target = date(2099, 2, 3)
        StationWeeklySchedule.objects.create(station=station, weekday=target.weekday(), work_start=time(9), work_end=time(18))
        start = timezone.make_aware(timezone.datetime(2099, 2, 3, 10))
        appointment = Appointment.objects.create(station=station, user=client_user, car=car, start=start, end=start, name="Client")
        buffer = BytesIO()
        Image.new("RGB", (10, 10), "white").save(buffer, format="JPEG")
        photo = AppointmentPhoto.objects.create(
            appointment=appointment,
            image=SimpleUploadedFile("operator-visible.jpg", buffer.getvalue(), content_type="image/jpeg"),
        )

        self.client.login(username="media-operator", password="test-password")
        response = self.client.get(reverse("protected_media", kwargs={"path": photo.image.name}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
