from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

import booking.admin_safety  # noqa: F401 - ensure safe registrations are active


class AdminUserPhoneValidationTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="phone-admin@example.com",
            email="phone-admin@example.com",
            password="Admin-password-123!",
        )
        self.user = User.objects.create_user(
            username="phone-user@example.com",
            email="phone-user@example.com",
            password="User-password-123!",
        )
        self.factory = RequestFactory()
        self.user_admin = admin.site._registry[User]

    def _request(self):
        request = self.factory.post("/admin/auth/user/")
        request.user = self.superuser
        return request

    def _change_form(self, phone):
        form_class = self.user_admin.get_form(self._request(), obj=self.user)
        return form_class(
            data={
                "username": self.user.username,
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "email": self.user.email,
                "phone": phone,
                "is_active": "on",
            },
            instance=self.user,
        )

    def test_admin_user_change_rejects_invalid_phone(self):
        form = self._change_form("123")

        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)

    def test_admin_user_change_normalizes_phone_before_saving_profile(self):
        form = self._change_form("8 912 345-67-89")
        self.assertTrue(form.is_valid(), form.errors)

        obj = form.save(commit=False)
        self.user_admin.save_model(self._request(), obj, form, change=True)

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.phone, "+79123456789")

    def test_admin_user_creation_form_uses_same_phone_rules(self):
        valid_form = self.user_admin.add_form(data={
            "username": "new-phone-user@example.com",
            "email": "new-phone-user@example.com",
            "first_name": "Иван",
            "last_name": "Иванов",
            "phone": "9123456789",
            "password1": "Strong-new-user-123!",
            "password2": "Strong-new-user-123!",
        })
        self.assertTrue(valid_form.is_valid(), valid_form.errors)
        self.assertEqual(valid_form.cleaned_data["phone"], "+79123456789")

        invalid_form = self.user_admin.add_form(data={
            "username": "bad-phone-user@example.com",
            "email": "bad-phone-user@example.com",
            "phone": "+7 212 345-67-89",
            "password1": "Strong-new-user-123!",
            "password2": "Strong-new-user-123!",
        })
        self.assertFalse(invalid_form.is_valid())
        self.assertIn("phone", invalid_form.errors)
