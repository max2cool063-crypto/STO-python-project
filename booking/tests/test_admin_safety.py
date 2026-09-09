from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
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

        # Keep model-level delete permission enabled so the Admin/Jazzmin UI can
        # expose the per-object delete control, while bulk deletion stays hidden.
        self.assertTrue(brand_admin.has_delete_permission(request))
        self.assertTrue(brand_admin.has_delete_permission(request, brand))
        self.assertNotIn("delete_selected", brand_admin.get_actions(request))

        delete_url = reverse("admin:booking_brand_delete", args=[brand.pk])
        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(delete_url, {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Brand.objects.filter(pk=brand.pk).exists())

        protected_brand = Brand.objects.create(name="Brand with model")
        CarModel.objects.create(brand=protected_brand, name="Unused model")

        self.assertFalse(brand_admin.has_delete_permission(request, protected_brand))
        response = self.client.get(
            reverse("admin:booking_brand_delete", args=[protected_brand.pk])
        )
        self.assertEqual(response.status_code, 403)
        with self.assertRaises(PermissionDenied):
            brand_admin.delete_model(request, protected_brand)
        self.assertTrue(Brand.objects.filter(pk=protected_brand.pk).exists())

    def test_car_model_delete_is_blocked_when_used_by_car(self):
        request = self._request()
        model_admin = admin.site._registry[CarModel]
        brand = Brand.objects.create(name="Vehicle brand")
        car_model = CarModel.objects.create(brand=brand, name="Unused vehicle model")

        self.assertTrue(model_admin.has_delete_permission(request))
        self.assertTrue(model_admin.has_delete_permission(request, car_model))
        self.assertNotIn("delete_selected", model_admin.get_actions(request))

        delete_url = reverse("admin:booking_carmodel_delete", args=[car_model.pk])
        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(delete_url, {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CarModel.objects.filter(pk=car_model.pk).exists())

        protected_model = CarModel.objects.create(
            brand=brand,
            name="Vehicle model in use",
        )
        Car.objects.create(
            owner=self.owner,
            model=protected_model,
            plate_number="А123ВС77",
        )

        self.assertFalse(model_admin.has_delete_permission(request, protected_model))
        response = self.client.get(
            reverse("admin:booking_carmodel_delete", args=[protected_model.pk])
        )
        self.assertEqual(response.status_code, 403)
        with self.assertRaises(PermissionDenied):
            model_admin.delete_model(request, protected_model)
        self.assertTrue(CarModel.objects.filter(pk=protected_model.pk).exists())

    def test_car_model_bulk_delete_removes_only_unused_models(self):
        request = self._request()
        model_admin = admin.site._registry[CarModel]
        actions = model_admin.get_actions(request)
        self.assertIn("delete_unused_models", actions)
        self.assertNotIn("delete_selected", actions)

        brand = Brand.objects.create(name="Bulk cleanup brand")
        unused_one = CarModel.objects.create(brand=brand, name="Unused one")
        unused_two = CarModel.objects.create(brand=brand, name="Unused two")
        protected_model = CarModel.objects.create(brand=brand, name="Used model")
        Car.objects.create(
            owner=self.owner,
            model=protected_model,
            plate_number="В456ОР77",
        )

        changelist_url = reverse("admin:booking_carmodel_changelist")
        selected = [unused_one.pk, unused_two.pk, protected_model.pk]
        action_data = {
            "action": "delete_unused_models",
            "_selected_action": selected,
        }

        response = self.client.post(changelist_url, action_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Будут удалены")
        self.assertContains(response, "используются автомобилями и удалены не будут")
        self.assertContains(response, str(protected_model))

        response = self.client.post(
            changelist_url,
            {**action_data, "apply": "yes"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CarModel.objects.filter(pk=unused_one.pk).exists())
        self.assertFalse(CarModel.objects.filter(pk=unused_two.pk).exists())
        self.assertTrue(CarModel.objects.filter(pk=protected_model.pk).exists())
        self.assertContains(response, "Удалено моделей: 2")
        self.assertContains(
            response,
            "Не удалены модели, которые используются автомобилями",
        )
        self.assertContains(response, str(protected_model))

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
