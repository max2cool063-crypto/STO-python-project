from django.contrib import admin
from django.contrib.auth.models import User
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

import booking.admin_safety  # noqa: F401 - ensure safety registrations are applied
from booking.models import Appointment, Brand, Car, CarModel, Station


class AdminSafetyTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="root@example.com",
            email="root@example.com",
            password="Admin-password-123!",
        )
        self.owner = User.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="Owner-password-123!",
        )
        self.client = Client()
        self.client.force_login(self.superuser)
        self.factory = RequestFactory()

    def _request(self):
        request = self.factory.get("/admin/")
        request.user = self.superuser
        return request

    def test_historical_models_do_not_allow_hard_delete(self):
        request = self._request()

        for model in (Station, Appointment, Car, User):
            model_admin = admin.site._registry[model]
            self.assertFalse(
                model_admin.has_delete_permission(request),
                msg=f"{model.__name__} unexpectedly allows hard delete",
            )
            self.assertNotIn("delete_selected", model_admin.get_actions(request))

    def test_direct_station_delete_view_is_forbidden(self):
        station = Station.objects.create(name="Protected station", address="Test address")

        response = self.client.get(
            reverse("admin:booking_station_delete", args=[station.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Station.objects.filter(pk=station.pk).exists())

    def test_direct_user_delete_view_is_forbidden_even_without_history(self):
        disposable_user = User.objects.create_user(
            username="disposable@example.com",
            password="Disposable-password-123!",
        )

        response = self.client.get(
            reverse("admin:auth_user_delete", args=[disposable_user.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.filter(pk=disposable_user.pk).exists())

    def test_appointment_status_is_not_quick_editable(self):
        appointment_admin = admin.site._registry[Appointment]

        self.assertEqual(appointment_admin.list_editable, ())
        self.assertIn("status", appointment_admin.list_display)

    def test_brand_delete_requires_models_to_be_removed_first(self):
        request = self._request()
        brand_admin = admin.site._registry[Brand]
        brand = Brand.objects.create(name="Unused brand")

        self.assertTrue(brand_admin.has_delete_permission(request, brand))
        self.assertNotIn("delete_selected", brand_admin.get_actions(request))

        CarModel.objects.create(brand=brand, name="Unused model")

        self.assertFalse(brand_admin.has_delete_permission(request, brand))

    def test_car_model_delete_is_blocked_when_used_by_car(self):
        request = self._request()
        model_admin = admin.site._registry[CarModel]
        brand = Brand.objects.create(name="Vehicle brand")
        car_model = CarModel.objects.create(brand=brand, name="Vehicle model")

        self.assertTrue(car_model is not None)
        self.assertTrue(admin.site._registry[CarModel].has_delete_permission(request, car_model))
        self.assertNotIn("delete_selected", admin.site._registry[CarModel].get_actions(request))

        Car.objects.create(
            owner=self.owner,
            model=car_model,
            plate_number="А123ВС77",
        )

        self.assertFalse(admin.site._registry[CarModel].has_delete_permission(request, car_model))

    def test_car_admin_rejects_invalid_plate_and_vin(self):
        brand = Brand.objects.create(name="Admin Vehicle Brand")
        car_model = CarModel.objects.create(brand=brand, name="Admin Vehicle Model")
        car_admin = admin.site._registry[Car]
        form_class = car_admin.get_form(self._request())

        form = form_class(data={
            "owner": self.owner.pk,
            "model": car_model.pk,
            "plate_number": "A123AA",
            "vin": "123",
            "is_active": "on",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("plate_number", form.errors)
        self.assertIn("vin", form.errors)

    def test_car_admin_normalizes_valid_plate_and_vin(self):
        brand = Brand.objects.create(name="Admin Normalization Brand")
        car_model = CarModel.objects.create(brand=brand, name="Admin Normalization Model")
        car_admin = admin.site._registry[Car]
        form_class = car_admin.get_form(self._request())

        form = form_class(data={
            "owner": self.owner.pk,
            "model": car_model.pk,
            "plate_number": "а123вс77",
            "vin": "xta210990y1234567",
            "is_active": "on",
        })

        self.assertTrue(form.is_valid(), form.errors)
        car = form.save()
        self.assertEqual(car.plate_number, "А123ВС77")
        self.assertEqual(car.vin, "XTA210990Y1234567")
