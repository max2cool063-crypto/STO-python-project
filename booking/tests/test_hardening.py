from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from booking.models import Appointment, AppointmentPhoto, Brand, Car, CarModel, Station, StationStaff, StationWeeklySchedule
from datetime import date, time
from django.utils import timezone


class PasswordSetupTests(TestCase):
    @patch("booking.views.auth.send_mail")
    def test_registration_sends_setup_link_and_never_password(self, send_mail):
        response = self.client.post(reverse("register"), {"email": "new@example.com"})

        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(email="new@example.com")
        self.assertFalse(user.has_usable_password())
        send_mail.assert_called_once()
        body = send_mail.call_args.args[1]
        self.assertIn("accounts/set-password/", body)
        self.assertNotIn("Пароль:", body)

    @patch("booking.views.auth.send_mail")
    def test_registration_resends_reset_link_for_existing_account(self, send_mail):
        user = User.objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
            password="Old-password-123!",
        )

        response = self.client.post(reverse("register"), {"email": "EXISTING@example.com"})

        self.assertRedirects(response, reverse("login"))
        send_mail.assert_called_once()
        body = send_mail.call_args.args[1]
        self.assertIn("accounts/set-password/", body)
        self.assertNotIn("Old-password-123!", body)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_response = self.client.post(
            reverse("set_password", kwargs={"uidb64": uid, "token": token}),
            {"password": "New-password-456!", "confirmation": "New-password-456!"},
        )

        self.assertRedirects(reset_response, reverse("login"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("New-password-456!"))
        self.assertFalse(user.check_password("Old-password-123!"))

    @patch("booking.views.auth.send_mail")
    def test_set_password_activates_account(self, send_mail):
        user = User.objects.create_user(
            username="new@example.com",
            email="new@example.com",
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        response = self.client.post(
            reverse("set_password", kwargs={"uidb64": uid, "token": token}),
            {"password": "Strong-password-123!", "confirmation": "Strong-password-123!"},
        )

        self.assertRedirects(response, reverse("login"))
        user.refresh_from_db()
        self.assertTrue(user.has_usable_password())
        self.assertTrue(user.check_password("Strong-password-123!"))


class AuthRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("booking.views.auth.send_mail")
    def test_registration_is_throttled_after_five_requests(self, send_mail):
        for index in range(5):
            response = self.client.post(reverse("register"), {"email": f"user{index}@example.com"})
            self.assertNotEqual(response.status_code, 429)

        response = self.client.post(reverse("register"), {"email": "blocked@example.com"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "3600")
        self.assertFalse(User.objects.filter(email="blocked@example.com").exists())

    def test_login_is_throttled_after_ten_failed_attempts(self):
        User.objects.create_user(
            username="login@example.com",
            email="login@example.com",
            password="Correct-password-123!",
        )

        for _ in range(10):
            response = self.client.post(
                reverse("login"),
                {"username": "login@example.com", "password": "Wrong-password-123!"},
            )
            self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("login"),
            {"username": "login@example.com", "password": "Wrong-password-123!"},
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "900")

    def test_successful_login_clears_failed_attempts(self):
        User.objects.create_user(
            username="success@example.com",
            email="success@example.com",
            password="Correct-password-123!",
        )

        for _ in range(3):
            response = self.client.post(
                reverse("login"),
                {"username": "success@example.com", "password": "Wrong-password-123!"},
            )
            self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("login"),
            {"username": "success@example.com", "password": "Correct-password-123!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("post_login_redirect"))
        self.assertTrue("_auth_user_id" in self.client.session)

        self.client.logout()
        response = self.client.post(
            reverse("login"),
            {"username": "success@example.com", "password": "Wrong-password-123!"},
        )
        self.assertEqual(response.status_code, 200)


class ProtectedMediaStaffTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="client@example.com",
            email="client@example.com",
            password="test-password",
        )
        self.staff_user = User.objects.create_user(
            username="operator@example.com",
            email="operator@example.com",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="test-password",
        )
        self.station = Station.objects.create(name="Station A")
        StationStaff.objects.create(
            station=self.station,
            user=self.staff_user,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        brand = Brand.objects.create(name="Test")
        model = CarModel.objects.create(brand=brand, name="Passenger", vehicle_type="CAR")
        self.car = Car.objects.create(owner=self.client_user, model=model, plate_number="A111AA")
        target = date(2099, 2, 3)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=target.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        start = timezone.make_aware(timezone.datetime(2099, 2, 3, 10, 0))
        self.appointment = Appointment.objects.create(
            user=self.client_user,
            car=self.car,
            station=self.station,
            start=start,
            end=start,
            name="Client",
        )

    @override_settings(MEDIA_ROOT="/tmp/sto-test-media")
    def test_station_staff_is_allowed_to_request_station_photo(self):
        photo = AppointmentPhoto.objects.create(
            appointment=self.appointment,
            image="appointments/station-photo.jpg",
        )
        self.client.login(username="operator@example.com", password="test-password")
        response = self.client.get(reverse("protected_media", kwargs={"path": photo.image.name}))
        # Access control must pass; the fixture file itself is intentionally absent.
        self.assertEqual(response.status_code, 404)


class PhotoValidationTests(TestCase):
    def test_booking_form_requires_real_image_content(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from booking.forms import PhotosUploadForm

        fake = SimpleUploadedFile(
            "fake.jpg",
            b"not an image",
            content_type="image/jpeg",
        )
        errors = PhotosUploadForm.validate_photos([fake])
        self.assertTrue(errors)
        self.assertIn("корректным изображением", errors[0])
