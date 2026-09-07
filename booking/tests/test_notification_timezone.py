from datetime import date, time

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings

from booking.models import Appointment, Brand, Car, CarModel, Notification, Station, StationSchedule, StationStaff
from booking.notifications import (
    create_station_staff_cancellation_notifications,
    create_station_staff_notifications,
    notify_client_booked,
    notify_client_cancelled,
    notify_client_reminder,
    notify_station_staff_booked,
    notify_station_staff_cancelled,
)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NotificationTimezoneTests(TestCase):
    def setUp(self):
        self.station = Station.objects.create(
            name="Самара Тест",
            address="Самара",
            timezone="Europe/Samara",
        )
        self.target_date = date(2099, 9, 3)
        StationSchedule.objects.create(
            station=self.station,
            date=self.target_date,
            work_start=time(9, 0),
            work_end=time(18, 0),
        )

        self.client_user = User.objects.create_user(
            username="samara-client",
            email="client@example.com",
        )
        self.owner = User.objects.create_user(
            username="samara-owner",
            email="owner@example.com",
        )
        StationStaff.objects.create(
            station=self.station,
            user=self.owner,
            role=StationStaff.ROLE_OWNER,
            is_active=True,
            receive_notifications=True,
        )

        brand = Brand.objects.create(name="Timezone Brand")
        model = CarModel.objects.create(brand=brand, name="Timezone Model")
        car = Car.objects.create(
            owner=self.client_user,
            model=model,
            plate_number="А123АА63",
        )
        start = self.station.make_local_datetime(self.target_date, time(10, 0))
        appointment = Appointment.objects.create(
            station=self.station,
            user=self.client_user,
            car=car,
            start=start,
            end=start,
            name="Иванов Иван",
            phone="+79990000000",
        )
        self.appointment = Appointment.objects.select_related(
            "station",
            "user",
            "car__model__brand",
        ).get(pk=appointment.pk)

    def test_all_email_notifications_render_station_local_time(self):
        notify_client_booked(self.appointment)
        notify_client_cancelled(self.appointment, cancelled_by_station=True)
        self.assertTrue(notify_client_reminder(self.appointment))
        notify_station_staff_booked(self.appointment)
        notify_station_staff_cancelled(self.appointment)

        self.assertEqual(len(mail.outbox), 5)
        for message in mail.outbox:
            self.assertIn("10:00", message.body)
            self.assertNotIn("06:00", message.body)

    def test_internal_notifications_render_local_time_and_use_declared_cancel_type(self):
        self.assertEqual(create_station_staff_notifications(self.appointment), 1)
        self.assertEqual(create_station_staff_cancellation_notifications(self.appointment), 1)

        booked = Notification.objects.get(
            appointment=self.appointment,
            notification_type=Notification.TYPE_NEW_APPOINTMENT,
        )
        cancelled = Notification.objects.get(
            appointment=self.appointment,
            notification_type=Notification.TYPE_APPOINTMENT_CANCELLED,
        )

        self.assertIn("10:00", booked.message)
        self.assertIn("10:00", cancelled.message)
        self.assertNotIn("06:00", booked.message)
        self.assertNotIn("06:00", cancelled.message)
        self.assertEqual(cancelled.get_notification_type_display(), "Запись отменена")
        cancelled.full_clean()
