from datetime import datetime, time

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import (
    Appointment,
    Brand,
    Car,
    CarModel,
    Notification,
    Station,
    StationStaff,
    StationWeeklySchedule,
)


class ClientCancellationNotificationTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="cancel-client",
            email="client@example.com",
        )
        self.owner = User.objects.create_user(
            username="cancel-owner",
            email="owner@example.com",
        )
        self.operator = User.objects.create_user(
            username="cancel-operator",
            email="operator@example.com",
        )
        self.station = Station.objects.create(name="Cancellation Station")
        StationStaff.objects.create(
            station=self.station,
            user=self.owner,
            role=StationStaff.ROLE_OWNER,
            is_active=True,
            receive_notifications=True,
        )
        StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
            receive_notifications=True,
        )
        self.brand = Brand.objects.create(name="Cancel Brand")
        self.model = CarModel.objects.create(brand=self.brand, name="Cancel Model", vehicle_type="CAR")
        self.car = Car.objects.create(
            owner=self.client_user,
            model=self.model,
            plate_number="А123АА63",
            vin="XTA210990Y1234567",
        )
        target = datetime(2099, 4, 7, 10, 0)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=target.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        self.appointment = Appointment.objects.create(
            station=self.station,
            user=self.client_user,
            car=self.car,
            start=timezone.make_aware(target),
            end=timezone.make_aware(datetime(2099, 4, 7, 10, 30)),
            name="Клиент",
            phone="+79990001122",
            vin=self.car.vin,
        )

    def test_client_cancellation_notifies_owner_and_operator(self):
        self.client.login(username="cancel-client", password="test-password")
        response = self.client.post(
            reverse("cabinet_cancel_appointment", kwargs={"pk": self.appointment.pk})
        )

        self.assertRedirects(response, reverse("cabinet_appointments"))
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "CANCELLED")

        notifications = Notification.objects.filter(appointment=self.appointment).order_by("recipient_id")
        self.assertEqual(notifications.count(), 2)
        self.assertEqual(
            set(notifications.values_list("recipient_id", flat=True)),
            {self.owner.pk, self.operator.pk},
        )
        self.assertEqual(set(notifications.values_list("title", flat=True)), {"Клиент отменил запись"})

        recipients = {message.to[0] for message in mail.outbox}
        self.assertIn("owner@example.com", recipients)
        self.assertIn("operator@example.com", recipients)

    def test_staff_with_disabled_notifications_receives_nothing(self):
        StationStaff.objects.filter(user=self.operator, station=self.station).update(receive_notifications=False)
        self.client.login(username="cancel-client", password="test-password")

        self.client.post(
            reverse("cabinet_cancel_appointment", kwargs={"pk": self.appointment.pk})
        )

        self.assertEqual(
            set(Notification.objects.filter(appointment=self.appointment).values_list("recipient_id", flat=True)),
            {self.owner.pk},
        )
        recipients = {message.to[0] for message in mail.outbox}
        self.assertNotIn("operator@example.com", recipients)
        self.assertIn("owner@example.com", recipients)
