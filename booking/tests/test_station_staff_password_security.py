from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from booking.models import Station, StationStaff


class StationStaffPasswordSecurityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="staff-owner",
            password="OwnerPassword!42",
        )
        self.operator = User.objects.create_user(
            username="staff-operator",
            password="OperatorPassword!42",
        )
        self.station = Station.objects.create(name="Password Station")
        StationStaff.objects.create(
            station=self.station,
            user=self.owner,
            role=StationStaff.ROLE_OWNER,
            is_active=True,
        )
        StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )

    def login_owner(self):
        self.client.login(username="staff-owner", password="OwnerPassword!42")

    def test_owner_cannot_set_numeric_password_for_operator(self):
        self.login_owner()

        response = self.client.post(
            reverse("station_staff", kwargs={"station_id": self.station.id}),
            {
                "action": "reset_password",
                "member_id": StationStaff.objects.get(user=self.operator).pk,
                "new_password": "12345678",
            },
        )

        self.assertRedirects(response, reverse("station_staff", kwargs={"station_id": self.station.id}))
        self.assertTrue(self.operator.check_password("OperatorPassword!42"))
        self.assertFalse(self.operator.check_password("12345678"))

    def test_owner_can_set_password_passing_django_validators(self):
        self.login_owner()
        new_password = "N7!qP4#xZ2mL"

        response = self.client.post(
            reverse("station_staff", kwargs={"station_id": self.station.id}),
            {
                "action": "reset_password",
                "member_id": StationStaff.objects.get(user=self.operator).pk,
                "new_password": new_password,
            },
        )

        self.assertRedirects(response, reverse("station_staff", kwargs={"station_id": self.station.id}))
        self.operator.refresh_from_db()
        self.assertTrue(self.operator.check_password(new_password))
