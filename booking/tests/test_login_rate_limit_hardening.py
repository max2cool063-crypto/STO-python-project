from unittest.mock import patch

from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.urls import reverse

from booking.security import LOGIN_IP_RATE_LIMIT, RateLimit


class AggregateLoginRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_rotating_usernames_cannot_bypass_ip_wide_failed_login_budget(self):
        for index in range(LOGIN_IP_RATE_LIMIT.limit):
            response = self.client.post(
                reverse("login"),
                {
                    "username": f"missing-user-{index}@example.com",
                    "password": "Wrong-password-123!",
                },
            )
            self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("login"),
            {
                "username": "one-more-missing-user@example.com",
                "password": "Wrong-password-123!",
            },
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], str(LOGIN_IP_RATE_LIMIT.window))


class RateLimitExpirySafetyTests(TestCase):
    def test_increment_refreshes_expiry_if_redis_recreates_an_expired_key(self):
        limiter = RateLimit("expiry-test", limit=5, window=123)
        request = RequestFactory().post("/accounts/login/", REMOTE_ADDR="192.0.2.10")

        with patch("booking.security.cache") as mocked_cache:
            mocked_cache.add.return_value = False
            mocked_cache.incr.return_value = 1

            result = limiter.hit(request, "identity")

        self.assertEqual(result, 1)
        mocked_cache.touch.assert_called_once_with(limiter._key(request, "identity"), 123)

    def test_locmem_expiry_between_add_and_increment_is_recovered(self):
        limiter = RateLimit("expiry-test", limit=5, window=123)
        request = RequestFactory().post("/accounts/login/", REMOTE_ADDR="192.0.2.11")

        with patch("booking.security.cache") as mocked_cache:
            mocked_cache.add.side_effect = [False, True]
            mocked_cache.incr.side_effect = ValueError("Key not found")

            result = limiter.hit(request, "identity")

        self.assertEqual(result, 1)
        self.assertEqual(mocked_cache.add.call_count, 2)
