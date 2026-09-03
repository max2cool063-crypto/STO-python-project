from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from booking.models import Station, StationStaff


class StationStaffProfileTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="Strong-owner-123!",
        )
        self.station = Station.objects.create(name="Test Station")
        self.owner_staff = StationStaff.objects.create(
            station=self.station,
            user=self.owner,
            role=StationStaff.ROLE_OWNER,
            is_active=True,
        )
        self.client.login(username="owner@example.com", password="Strong-owner-123!")

    def test_owner_can_create_operator_with_profile_data(self):
        response = self.client.post(
            reverse("station_staff_create_operator", kwargs={"station_id": self.station.pk}),
            {
                "login": "operator@example.com",
                "password": "Strong-operator-123!",
                "first_name": "Иван",
                "last_name": "Иванов",
                "email": "operator@example.com",
                "phone": "89001234567",
            },
        )
        self.assertRedirects(response, reverse("station_staff", kwargs={"station_id": self.station.pk}))
        operator = User.objects.get(username="operator@example.com")
        self.assertEqual(operator.email, "operator@example.com")
        self.assertEqual(operator.first_name, "Иван")
        self.assertEqual(operator.last_name, "Иванов")
        self.assertEqual(operator.profile.phone, "+79001234567")
        self.assertTrue(
            StationStaff.objects.filter(
                station=self.station, user=operator, role=StationStaff.ROLE_OPERATOR
            ).exists()
        )

    def test_owner_cannot_create_operator_with_invalid_phone(self):
        response = self.client.post(
            reverse("station_staff_create_operator", kwargs={"station_id": self.station.pk}),
            {
                "login": "operator-invalid-phone",
                "password": "Strong-operator-123!",
                "first_name": "Иван",
                "last_name": "Иванов",
                "email": "operator-invalid-phone@example.com",
                "phone": "12345678901",
            },
        )
        self.assertRedirects(response, reverse("station_staff", kwargs={"station_id": self.station.pk}))
        self.assertFalse(User.objects.filter(username="operator-invalid-phone").exists())

    def test_owner_can_edit_operator_profile(self):
        operator = User.objects.create_user(
            username="operator2",
            email="old@example.com",
            password="Strong-operator-123!",
            first_name="Старое",
            last_name="Имя",
        )
        operator.profile.phone = "+70000000000"
        operator.profile.save()
        member = StationStaff.objects.create(
            station=self.station,
            user=operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
            created_by=self.owner,
        )

        response = self.client.post(
            reverse("station_staff_edit_profile", kwargs={"station_id": self.station.pk, "member_id": member.pk}),
            {
                "first_name": "Пётр",
                "last_name": "Петров",
                "email": "new@example.com",
                "phone": "89991234567",
            },
        )
        self.assertRedirects(response, reverse("station_staff", kwargs={"station_id": self.station.pk}))
        operator.refresh_from_db()
        self.assertEqual(operator.email, "new@example.com")
        self.assertEqual(operator.first_name, "Пётр")
        self.assertEqual(operator.last_name, "Петров")
        self.assertEqual(operator.profile.phone, "+79991234567")

    def test_owner_can_edit_own_profile(self):
        response = self.client.post(
            reverse("station_staff_edit_profile", kwargs={"station_id": self.station.pk, "member_id": self.owner_staff.pk}),
            {
                "first_name": "Александр",
                "last_name": "Николаев",
                "email": "owner-new@example.com",
                "phone": "+79990001122",
            },
        )
        self.assertRedirects(response, reverse("station_staff", kwargs={"station_id": self.station.pk}))
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.email, "owner-new@example.com")
        self.assertEqual(self.owner.first_name, "Александр")
        self.assertEqual(self.owner.last_name, "Николаев")
        self.assertEqual(self.owner.profile.phone, "+79990001122")


class RsaImportedStationTests(TestCase):
    def test_rsa_imported_station_is_inactive(self):
        station = Station.objects.create(
            name="RSA Station",
            address="Самара, тестовый адрес",
            rsa_id="RSA-12345",
        )
        station.refresh_from_db()
        self.assertFalse(station.is_active)

    def test_regular_station_remains_active(self):
        station = Station.objects.create(name="Manual Station")
        self.assertTrue(station.is_active)
