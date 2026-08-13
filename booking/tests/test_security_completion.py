from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from booking.models import Brand, Car, CarModel, Station, StationStaff


class SecurityCompletionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner@example.com", password="pass")
        self.other_user = User.objects.create_user(username="other@example.com", password="pass")
        self.staff_user = User.objects.create_user(username="staff@example.com", password="pass")
        self.brand = Brand.objects.create(name="Test Brand")
        self.other_brand = Brand.objects.create(name="Other Brand")
        self.model = CarModel.objects.create(brand=self.brand, name="Test Model", vehicle_type="CAR")
        self.other_model = CarModel.objects.create(brand=self.other_brand, name="Other Model", vehicle_type="CAR")
        self.station = Station.objects.create(name="Station A", address="A")
        StationStaff.objects.create(
            station=self.station, user=self.staff_user,
            role=StationStaff.ROLE_OPERATOR, is_active=True,
        )
        self.car = Car.objects.create(
            owner=self.user, model=self.model, plate_number="A111AA", vin="VIN111", is_active=True
        )
        self.inactive_car = Car.objects.create(
            owner=self.user, model=self.model, plate_number="A222AA", vin="VIN222", is_active=False
        )
        self.other_car = Car.objects.create(
            owner=self.other_user, model=self.model, plate_number="B111BB", vin="VIN333", is_active=True
        )

    def test_car_create_ignores_submitted_owner_id(self):
        client = Client()
        client.login(username="owner@example.com", password="pass")
        response = client.post(reverse("cabinet_cars"), {
            "owner": self.other_user.id,
            "model": self.model.id,
            "plate": "A999AA",
            "vin": "VIN999",
        })
        self.assertEqual(response.status_code, 302)
        created = Car.objects.get(plate_number="A999AA")
        self.assertEqual(created.owner_id, self.user.id)

    def test_inactive_car_is_rejected_by_station_slots_api(self):
        client = Client()
        client.login(username="owner@example.com", password="pass")
        response = client.get(
            reverse("station_slots_api", kwargs={"station_id": self.station.id}),
            {"date": "2099-03-03", "car_id": self.inactive_car.id},
        )
        self.assertEqual(response.status_code, 404)

    def test_foreign_car_is_rejected_by_station_slots_api(self):
        client = Client()
        client.login(username="owner@example.com", password="pass")
        response = client.get(
            reverse("station_slots_api", kwargs={"station_id": self.station.id}),
            {"date": "2099-03-03", "car_id": self.other_car.id},
        )
        self.assertEqual(response.status_code, 404)

    def test_brands_api_is_available_and_models_are_scoped_to_brand(self):
        client = Client()
        response = client.get(reverse("brands_api"))
        self.assertEqual(response.status_code, 200)
        response = client.get(reverse("models_api", kwargs={"brand_id": self.brand.id}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        model_ids = [item.get("id") for item in data]
        self.assertIn(self.model.id, model_ids)
        self.assertNotIn(self.other_model.id, model_ids)

    def test_models_api_requires_valid_brand_route(self):
        response = self.client.get(reverse("models_api", kwargs={"brand_id": self.brand.id}))
        self.assertEqual(response.status_code, 200)
