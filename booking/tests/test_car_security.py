from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from booking.models import Brand, Car, CarModel


class CarSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="owner@example.com", password="test-password"
        )
        self.other_user = User.objects.create_user(
            username="other@example.com", password="test-password"
        )
        brand = Brand.objects.create(name="Test")
        model = CarModel.objects.create(
            brand=brand, name="Passenger", vehicle_type="CAR"
        )
        self.car = Car.objects.create(
            owner=self.user,
            model=model,
            plate_number="A111AA",
            vin="TESTVIN111",
            is_active=True,
        )
        self.other_car = Car.objects.create(
            owner=self.other_user,
            model=model,
            plate_number="B222BB",
            vin="TESTVIN222",
            is_active=True,
        )

    def test_client_cannot_edit_foreign_car(self):
        self.client.login(username="owner@example.com", password="test-password")
        response = self.client.get(
            reverse("cabinet_car_edit", kwargs={"pk": self.other_car.id})
        )
        self.assertEqual(response.status_code, 404)

    def test_client_cannot_delete_foreign_car(self):
        self.client.login(username="owner@example.com", password="test-password")
        response = self.client.post(
            reverse("cabinet_car_delete", kwargs={"pk": self.other_car.id})
        )
        self.assertEqual(response.status_code, 404)
        self.other_car.refresh_from_db()
        self.assertTrue(self.other_car.is_active)

    def test_client_can_edit_own_car(self):
        self.client.login(username="owner@example.com", password="test-password")
        response = self.client.get(
            reverse("cabinet_car_edit", kwargs={"pk": self.car.id})
        )
        self.assertEqual(response.status_code, 200)

    def test_cabinet_lists_only_active_owned_cars(self):
        inactive = Car.objects.create(
            owner=self.user,
            model=self.car.model,
            plate_number="C333CC",
            is_active=False,
        )
        self.client.login(username="owner@example.com", password="test-password")
        response = self.client.get(reverse("cabinet_cars"))
        self.assertEqual(response.status_code, 200)
        cars = list(response.context["cars"])
        self.assertIn(self.car, cars)
        self.assertNotIn(self.other_car, cars)
        self.assertNotIn(inactive, cars)

    def test_unauthenticated_user_cannot_access_cabinet_cars(self):
        response = self.client.get(reverse("cabinet_cars"))
        self.assertEqual(response.status_code, 302)

    def test_unauthenticated_user_cannot_edit_car(self):
        response = self.client.get(
            reverse("cabinet_car_edit", kwargs={"pk": self.car.id})
        )
        self.assertEqual(response.status_code, 302)
