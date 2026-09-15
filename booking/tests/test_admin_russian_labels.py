from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from booking.models import Brand, Car, CarModel, EmailOutbox


class RussianAdminLabelsTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("admin", "admin@example.com", "test-password"))

    def test_catalog_headers_and_filters(self):
        # Related-field filters are hidden until there are multiple choices.
        for name in ("Audi", "Honda"):
            model = CarModel.objects.create(brand=Brand.objects.create(name=name), name="Test")
            Car.objects.create(owner=User.objects.get(username="admin"), model=model, plate_number=name)
        for model, labels in {
            "car": ("Владелец", "Модель", "Марка"),
            "brand": ("Название марки",),
            "carmodel": ("Название модели", "Марка"),
        }.items():
            with self.subTest(model=model):
                response = self.client.get(reverse(f"admin:booking_{model}_changelist"))
                self.assertEqual(response.status_code, 200)
                # Empty lists omit column headings; the add form still exposes labels.
                form = self.client.get(reverse(f"admin:booking_{model}_add"))
                for label in labels:
                    self.assertIn(label, response.content.decode() + form.content.decode())

    def test_existing_email_codes_are_translated_in_list_and_details(self):
        item = EmailOutbox.objects.create(
            deduplication_key="russian-admin", kind="password", status="cancelled",
            subject="Test", body="Test", recipient="client@example.com",
            last_error="PasswordLinkInvalid",
        )
        for url in [reverse("admin:booking_emailoutbox_changelist"),
                    reverse("admin:booking_emailoutbox_change", args=[item.pk])]:
            response = self.client.get(url)
            for text in ["Тип письма", "Установка или восстановление пароля", "Последняя ошибка",
                         "Ссылка для установки пароля недействительна"]:
                self.assertContains(response, text)
        item.refresh_from_db()
        self.assertEqual(item.kind, "password")
        self.assertEqual(item.last_error, "PasswordLinkInvalid")

    def test_all_email_types_appear_in_filter_in_russian(self):
        response = self.client.get(reverse("admin:booking_emailoutbox_changelist"))
        for code, label in EmailOutbox.Kind.choices:
            self.assertContains(response, label)
