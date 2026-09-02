from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from booking.forms import CarForm, ProfileForm
from booking.models import Brand, Car, CarModel, UserProfile


class ClientInputValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="client@example.com",
            password="test-password",
        )
        self.profile = UserProfile.objects.get(user=self.user)
        brand = Brand.objects.create(name="Test")
        self.model = CarModel.objects.create(
            brand=brand,
            name="Passenger",
            vehicle_type="CAR",
        )
        self.client.login(username="client@example.com", password="test-password")

    def test_car_form_accepts_valid_russian_plate_and_vin(self):
        form = CarForm({
            "plate_number": "А123ВС77",
            "vin": "XTA210990Y1234567",
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["plate_number"], "А123ВС77")
        self.assertEqual(form.cleaned_data["vin"], "XTA210990Y1234567")

    def test_car_form_rejects_invalid_plate(self):
        for plate in ("A123AA", "А123ВВ", "А12ВС777", "А123ABC77"):
            with self.subTest(plate=plate):
                form = CarForm({"plate_number": plate, "vin": ""})
                self.assertFalse(form.is_valid())
                self.assertIn("plate_number", form.errors)

    def test_car_form_rejects_invalid_vin(self):
        for vin in ("123", "XTA210990Y123456", "XTA210990Y123456I", "XTA210990Y12345O7"):
            with self.subTest(vin=vin):
                form = CarForm({"plate_number": "А123ВС77", "vin": vin})
                self.assertFalse(form.is_valid())
                self.assertIn("vin", form.errors)

    def test_cabinet_car_creation_rejects_invalid_identifiers(self):
        response = self.client.post(
            reverse("cabinet_cars"),
            {
                "model": self.model.id,
                "plate": "A123AA",
                "vin": "123",
            },
        )
        self.assertRedirects(response, reverse("cabinet_cars"))
        self.assertFalse(Car.objects.filter(owner=self.user).exists())

    def test_cabinet_car_creation_accepts_valid_identifiers(self):
        response = self.client.post(
            reverse("cabinet_cars"),
            {
                "model": self.model.id,
                "plate": "А123ВС77",
                "vin": "XTA210990Y1234567",
            },
        )
        self.assertRedirects(response, reverse("cabinet_cars"))
        car = Car.objects.get(owner=self.user)
        self.assertEqual(car.plate_number, "А123ВС77")
        self.assertEqual(car.vin, "XTA210990Y1234567")

    def test_profile_form_normalizes_phone_from_8_to_plus_7(self):
        form = ProfileForm(
            {"first_name": "Иван", "last_name": "Иванов", "phone": "8 912 345-67-89"},
            user=self.user,
            profile=self.profile,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.phone, "+79123456789")

    def test_profile_form_normalizes_phone_without_country_code(self):
        form = ProfileForm(
            {"first_name": "Иван", "last_name": "Иванов", "phone": "9123456789"},
            user=self.user,
            profile=self.profile,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["phone"], "+79123456789")

    def test_profile_form_rejects_invalid_phone(self):
        for phone in ("123", "+7 212 345-67-89", "+7 912 345-67-890"):
            with self.subTest(phone=phone):
                form = ProfileForm(
                    {"first_name": "Иван", "last_name": "Иванов", "phone": phone},
                    user=self.user,
                    profile=self.profile,
                )
                self.assertFalse(form.is_valid())
                self.assertIn("phone", form.errors)
