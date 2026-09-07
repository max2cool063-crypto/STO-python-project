from datetime import date, time
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from booking.models import Appointment, AppointmentPhoto, Brand, Car, CarModel, Station, StationWeeklySchedule


class AppointmentMediaSecurityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="test-password",
        )
        self.station = Station.objects.create(name="Station A")
        self.brand = Brand.objects.create(name="Test")
        self.model = CarModel.objects.create(
            brand=self.brand,
            name="Passenger",
            vehicle_type="CAR",
        )
        self.car = Car.objects.create(
            owner=self.owner,
            model=self.model,
            plate_number="A111AA",
        )
        self.other_car = Car.objects.create(
            owner=self.other_user,
            model=self.model,
            plate_number="B222BB",
        )

    def create_appointment(self, user, car):
        target = date(2099, 2, 3)
        StationWeeklySchedule.objects.get_or_create(
            station=self.station,
            weekday=target.weekday(),
            defaults={"work_start": time(9, 0), "work_end": time(18, 0)},
        )
        start = timezone.make_aware(timezone.datetime(2099, 2, 3, 10, 0))
        return Appointment.objects.create(
            station=self.station,
            user=user,
            car=car,
            start=start,
            end=start,
            name="Client",
            phone="123",
        )

    def create_real_photo(self, appointment, filename):
        buffer = BytesIO()
        Image.new("RGB", (10, 10), "white").save(buffer, format="JPEG")
        return AppointmentPhoto.objects.create(
            appointment=appointment,
            image=SimpleUploadedFile(
                filename,
                buffer.getvalue(),
                content_type="image/jpeg",
            ),
        )

    def test_user_cannot_download_zip_of_foreign_appointment(self):
        appointment = self.create_appointment(self.other_user, self.other_car)
        self.client.login(username="owner@example.com", password="test-password")

        response = self.client.get(
            reverse("appointment_photos_zip", kwargs={"pk": appointment.id})
        )

        self.assertEqual(response.status_code, 404)

    def test_user_cannot_access_foreign_protected_media(self):
        appointment = self.create_appointment(self.other_user, self.other_car)
        photo = AppointmentPhoto.objects.create(
            appointment=appointment,
            image="appointments/foreign-secret.jpg",
        )
        self.client.login(username="owner@example.com", password="test-password")

        response = self.client.get(
            reverse("protected_media", kwargs={"path": photo.image.name})
        )

        self.assertEqual(response.status_code, 404)

    def test_staff_only_user_cannot_access_protected_media(self):
        appointment = self.create_appointment(self.other_user, self.other_car)
        photo = self.create_real_photo(appointment, "staff-only-denied.jpg")
        User.objects.create_user(
            username="staff-only@example.com",
            password="test-password",
            is_staff=True,
            is_superuser=False,
        )
        self.client.login(username="staff-only@example.com", password="test-password")

        response = self.client.get(
            reverse("protected_media", kwargs={"path": photo.image.name})
        )

        self.assertEqual(response.status_code, 404)

    def test_superuser_can_access_protected_media(self):
        appointment = self.create_appointment(self.other_user, self.other_car)
        photo = self.create_real_photo(appointment, "superuser-visible.jpg")
        User.objects.create_superuser(
            username="system-admin@example.com",
            email="system-admin@example.com",
            password="test-password",
        )
        self.client.login(username="system-admin@example.com", password="test-password")

        response = self.client.get(
            reverse("protected_media", kwargs={"path": photo.image.name})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")

    def test_owner_can_request_own_photo_zip(self):
        appointment = self.create_appointment(self.owner, self.car)
        AppointmentPhoto.objects.create(
            appointment=appointment,
            image="appointments/own-photo.jpg",
        )
        self.client.login(username="owner@example.com", password="test-password")

        response = self.client.get(
            reverse("appointment_photos_zip", kwargs={"pk": appointment.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
