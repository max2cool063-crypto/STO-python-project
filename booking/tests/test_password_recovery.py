from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from booking.models import EmailOutbox
from booking.security import REGISTRATION_RATE_LIMIT
from booking.views.auth import REGISTRATION_RESPONSE_MESSAGE


class PasswordRecoveryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.url = reverse("password_reset_request")

    def test_login_links_to_recovery_form(self):
        self.assertContains(self.client.get(reverse("login")), self.url)
        response = self.client.get(self.url)
        self.assertContains(response, "Восстановить пароль")
        self.assertNotContains(response, "Создать аккаунт")

    def test_existing_account_queues_reset_without_changing_password(self):
        user = User.objects.create_user("recover@example.com", "recover@example.com", "Current-password-123!")
        response = self.client.post(self.url, {"email": user.email}, follow=True)
        self.assertContains(response, REGISTRATION_RESPONSE_MESSAGE, count=1)
        job = EmailOutbox.objects.get(user=user, kind="password")
        self.assertEqual(job.status, EmailOutbox.Status.PENDING)
        self.assertTrue(job.auth_token)
        user.refresh_from_db()
        self.assertTrue(user.check_password("Current-password-123!"))

    def test_unknown_address_does_not_create_account_or_email(self):
        response = self.client.post(self.url, {"email": "unknown@example.com"}, follow=True)
        self.assertContains(response, REGISTRATION_RESPONSE_MESSAGE, count=1)
        self.assertFalse(User.objects.exists())
        self.assertFalse(EmailOutbox.objects.exists())

    def test_invalid_address_returns_to_recovery(self):
        response = self.client.post(self.url, {"email": "invalid"})
        self.assertRedirects(response, self.url)

    def test_recovery_uses_registration_rate_limit(self):
        for _ in range(REGISTRATION_RATE_LIMIT.limit):
            self.client.post(self.url, {"email": "unknown@example.com"})
        self.assertEqual(self.client.post(self.url, {"email": "unknown@example.com"}).status_code, 429)
