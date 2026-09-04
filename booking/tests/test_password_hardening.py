from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class PasswordChangeHardeningTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="Current-password-123!",
        )
        self.client.force_login(self.user)

    def test_password_change_uses_configured_password_validators(self):
        response = self.client.post(
            reverse("change_password"),
            {
                "current_password": "Current-password-123!",
                "new_password": "12345678",
                "confirm_password": "12345678",
            },
        )

        self.assertRedirects(response, reverse("cabinet"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Current-password-123!"))
        self.assertFalse(self.user.check_password("12345678"))
