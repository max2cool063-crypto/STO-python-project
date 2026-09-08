from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from booking.models import Station, StationStaff


class StationStaffEmailValidationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="email-validation-owner",
            password="Strong-owner-123!",
        )
        self.station = Station.objects.create(name="Email Validation Station")
        StationStaff.objects.create(
            station=self.station,
            user=self.owner,
            role=StationStaff.ROLE_OWNER,
            is_active=True,
        )
        self.client.login(
            username="email-validation-owner",
            password="Strong-owner-123!",
        )

    def test_owner_cannot_create_operator_with_malformed_email(self):
        response = self.client.post(
            reverse("station_staff_create_operator", kwargs={"station_id": self.station.pk}),
            {
                "login": "bad-email-operator",
                "password": "Strong-operator-123!",
                "email": "not-an-email",
                "phone": "+79990001122",
            },
        )

        self.assertRedirects(
            response,
            reverse("station_staff", kwargs={"station_id": self.station.pk}),
        )
        self.assertFalse(User.objects.filter(username="bad-email-operator").exists())

    def test_owner_cannot_save_malformed_operator_email(self):
        operator = User.objects.create_user(
            username="editable-email-operator",
            email="valid@example.com",
            password="Strong-operator-123!",
        )
        member = StationStaff.objects.create(
            station=self.station,
            user=operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )

        url = reverse(
            "station_staff_edit_profile",
            kwargs={"station_id": self.station.pk, "member_id": member.pk},
        )
        response = self.client.post(
            url,
            {
                "email": "bad-email",
                "first_name": "Иван",
                "last_name": "Иванов",
                "phone": "+79990002233",
            },
        )

        self.assertRedirects(response, url)
        operator.refresh_from_db()
        self.assertEqual(operator.email, "valid@example.com")
