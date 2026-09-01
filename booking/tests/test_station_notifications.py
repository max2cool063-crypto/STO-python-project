from datetime import date, time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import (
    Appointment, Brand, Car, CarModel, Notification,
    Station, StationStaff, StationWeeklySchedule,
)


class StationNotificationTests(TestCase):
    def setUp(self):
        self.station = Station.objects.create(name="СТО Тест", address="Тестовый адрес")
        self.brand = Brand.objects.create(name="Test")
        self.model = CarModel.objects.create(brand=self.brand, name="Model")

        self.client_user = User.objects.create_user(
            username="client", email="client@example.com", first_name="Иван", last_name="Иванов"
        )
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", first_name="Ольга", last_name="Владелец"
        )
        self.operator = User.objects.create_user(
            username="operator", email="operator@example.com", first_name="Пётр", last_name="Оператор"
        )
        self.inactive_operator = User.objects.create_user(
            username="inactive", email="inactive@example.com"
        )
        StationStaff.objects.create(station=self.station, user=self.owner, role=StationStaff.ROLE_OWNER)
        StationStaff.objects.create(station=self.station, user=self.operator, role=StationStaff.ROLE_OPERATOR)
        StationStaff.objects.create(
            station=self.station, user=self.inactive_operator,
            role=StationStaff.ROLE_OPERATOR, is_active=False,
        )
        self.car = Car.objects.create(
            owner=self.client_user, model=self.model, plate_number="A123AA77", vin="TESTVIN123"
        )

        target = timezone.localdate() + timedelta(days=2)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=target.weekday(),
            work_start=time(8, 0),
            work_end=time(18, 0),
        )
        self.start = timezone.make_aware(timezone.datetime.combine(target, time(10, 0)))

    @patch("booking.views.booking.notify_client_booked")
    @patch("booking.views.booking.notify_station_staff_booked")
    def test_client_booking_creates_notifications_for_active_staff(self, _email_staff, _email_client):
        self.client.force_login(self.client_user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("book_station", args=[self.station.pk]),
                {"start": self.start.isoformat(), "car": self.car.pk},
            )

        self.assertRedirects(response, reverse("cabinet_appointments"))
        appointment = Appointment.objects.get(station=self.station)
        notifications = Notification.objects.filter(appointment=appointment).order_by("recipient_id")
        self.assertEqual(notifications.count(), 2)
        self.assertSetEqual(
            set(notifications.values_list("recipient_id", flat=True)),
            {self.owner.pk, self.operator.pk},
        )
        self.assertFalse(Notification.objects.filter(recipient=self.inactive_operator).exists())
        self.assertTrue(all(n.notification_type == Notification.TYPE_NEW_APPOINTMENT for n in notifications))

    def test_notification_list_returns_only_recipient_notifications(self):
        appointment = Appointment.objects.create(
            station=self.station,
            user=self.client_user,
            car=self.car,
            start=self.start,
            end=self.start,
            name="Иванов Иван",
            phone="+79990000000",
            vin=self.car.vin,
        )
        Notification.objects.create(
            recipient=self.owner,
            station=self.station,
            appointment=appointment,
            notification_type=Notification.TYPE_NEW_APPOINTMENT,
            title="Новая запись",
            message="Клиент: Иванов Иван",
        )
        Notification.objects.create(
            recipient=self.operator,
            station=self.station,
            appointment=appointment,
            notification_type=Notification.TYPE_NEW_APPOINTMENT,
            title="Новая запись",
            message="Клиент: Иванов Иван",
        )

        self.client.force_login(self.owner)
        response = self.client.get(reverse("station_notifications"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["unread_count"], 1)
        self.assertEqual(len(response.json()["notifications"]), 1)
        self.assertEqual(response.json()["notifications"][0]["appointment_url"], reverse(
            "station_appointment_detail", args=[self.station.pk, appointment.pk]
        ))

    def test_notification_read_requires_recipient(self):
        appointment = Appointment.objects.create(
            station=self.station,
            user=self.client_user,
            car=self.car,
            start=self.start,
            end=self.start,
            name="Иванов Иван",
        )
        notification = Notification.objects.create(
            recipient=self.owner,
            station=self.station,
            appointment=appointment,
            notification_type=Notification.TYPE_NEW_APPOINTMENT,
            title="Новая запись",
            message="Клиент: Иванов Иван",
        )

        self.client.force_login(self.operator)
        response = self.client.post(reverse("station_notification_read", args=[notification.pk]))
        self.assertEqual(response.status_code, 404)
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)
