from django.conf import settings
from django.http import HttpResponse
from django.middleware.security import SecurityMiddleware
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse


class DeploymentHealthTests(SimpleTestCase):
    def test_health_endpoint_is_registered(self):
        response = self.client.get(reverse("healthz"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_health_endpoint_is_the_only_explicit_ssl_redirect_exemption(self):
        self.assertEqual(settings.SECURE_REDIRECT_EXEMPT, [r"^healthz/$"])

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_REDIRECT_EXEMPT=[r"^healthz/$"],
    )
    def test_internal_http_health_probe_is_not_redirected_under_https_hardening(self):
        request = RequestFactory().get("/healthz/")
        middleware = SecurityMiddleware(
            lambda incoming_request: HttpResponse("ok")
        )

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
