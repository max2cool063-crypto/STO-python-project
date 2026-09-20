from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from booking.models import Station, StationStaff


class PasswordFeedbackTests(TestCase):
    current = "Current-password-123!"

    def assert_feedback(self, response, user, rejected):
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-password-error', html)
        self.assertGreater(html.index('data-password-error'), html.index('<form method="post">'))
        self.assertNotIn(f'value="{rejected}"', html)
        user.refresh_from_db()
        self.assertTrue(user.check_password(self.current))

    def test_client_and_staff_see_password_validation_inside_form(self):
        for role in (None, "OPERATOR", "OWNER"):
            user = User.objects.create_user(username=f"feedback-{role}", password=self.current)
            if role:
                StationStaff.objects.create(user=user, station=Station.objects.create(name=role), role=role)
            self.client.force_login(user)
            url = reverse("station_change_password" if role else "change_password")
            for rejected in ("abc", "password", "12345678"):
                with self.subTest(role=role, password=rejected):
                    response = self.client.post(url, {
                        "current_password": self.current, "new_password": rejected,
                        "confirm_password": rejected,
                    }, follow=True)
                    self.assert_feedback(response, user, rejected)

    def test_setup_link_shows_errors_and_remains_usable(self):
        user = User.objects.create_user(username="setup-feedback", password=self.current)
        url = reverse("set_password", args=[urlsafe_base64_encode(force_bytes(user.pk)),
                      default_token_generator.make_token(user)])
        for rejected in ("abc", "password", "12345678"):
            response = self.client.post(url, {"password": rejected, "confirmation": rejected})
            self.assert_feedback(response, user, rejected)
        accepted = "Unique-new-password-9847!"
        response = self.client.post(url, {"password": accepted, "confirmation": accepted})
        self.assertRedirects(response, reverse("login"))
        user.refresh_from_db()
        self.assertTrue(user.check_password(accepted))
