from datetime import date, time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from booking.models import Appointment, Brand, Car, CarModel, Station, StationStaff


class AppointmentBusinessLogicHardeningTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="client-hardening@example.com",
            password="test-password",
        )
        self.operator_user = User.objects.create_user(
            username="operator-hardening@example.com",
            password="test-password",
        )
        self.brand = Brand.objects.create(name="Hardening Test")
        self.passenger_model = CarModel.objects.create(
            brand=self.brand,
            name="Passenger",
            vehicle_type="CAR",
        )
        self.truck_model = CarModel.objects.create(
            brand=self.brand,
            name="Truck",
            vehicle_type="TRUCK",
        )
        self.passenger = Car.objects.create(
            owner=self.client_user,
            model=self.passenger_model,
            plate_number="A111AA",
        )
        self.truck = Car.objects.create(
            owner=self.client_user,
            model=self.truck_model,
            plate_number="B222BB",
        )
        self.station = Station.objects.create(
            name="Hardening Station",
            timezone="Europe/Moscow",
            slot_duration=30,
        )
        self.operator = StationStaff.objects.create(
            station=self.station,
            user=self.operator_user,
            role=StationStaff.ROLE_OPERATOR,
        )
        target = date(2099, 2, 3)
        from booking.models import StationWeeklySchedule

        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=target.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        self.start = timezone.make_aware(timezone.datetime(2099, 2, 3, 10, 0))

    def make_appointment(self, *, car=None, status="BOOKED"):
        car = car or self.passenger
        appointment = Appointment.objects.create(
            station=self.station,
            user=self.client_user,
            car=car,
            start=self.start,
            end=self.start + timedelta(minutes=30),
            name="Client",
            phone="+79991234567",
        )
        if status != "BOOKED":
            Appointment.objects.filter(pk=appointment.pk).update(status=status)
            appointment.refresh_from_db()
        return appointment

    @patch("booking.views.cabinet.create_station_staff_cancellation_notifications")
    @patch("booking.views.cabinet.notify_station_staff_cancelled")
    @patch("booking.views.cabinet.notify_client_cancelled")
    def test_client_cancel_is_atomic_and_notifies_after_commit(
        self, notify_client, notify_staff, create_notifications
    ):
        appointment = self.make_appointment()
        self.client.login(username="client-hardening@example.com", password="test-password")

        response = self.client.post(
            f"/cabinet/appointments/{appointment.pk}/cancel/",
        )

        self.assertRedirects(response, "/cabinet/appointments/")
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "CANCELLED")
        notify_client.assert_called_once_with(appointment, cancelled_by_station=False)
        notify_staff.assert_called_once_with(appointment)
        create_notifications.assert_called_once_with(appointment)

    @patch("booking.views.station_appointment_status.notify_client_cancelled")
    def test_station_status_change_locks_and_updates_appointment(self, notify_client):
        appointment = self.make_appointment()
        self.client.login(username="operator-hardening@example.com", password="test-password")

        response = self.client.post(
            f"/station/{self.station.pk}/appointments/{appointment.pk}/status/",
            {"status": "CANCELLED", "comment": "Клиент отменил запись"},
        )

        self.assertRedirects(response, f"/station/{self.station.pk}/appointments/")
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "CANCELLED")
        self.assertEqual(appointment.notes, "Клиент отменил запись")
        log = appointment.logs.get()
        self.assertEqual(log.old_status, "BOOKED")
        self.assertEqual(log.new_status, "CANCELLED")
        notify_client.assert_called_once_with(appointment, cancelled_by_station=True)

    def test_station_status_endpoint_rejects_terminal_appointment(self):
        appointment = self.make_appointment(status="DONE")
        self.client.login(username="operator-hardening@example.com", password="test-password")

        response = self.client.post(
            f"/station/{self.station.pk}/appointments/{appointment.pk}/status/",
            {"status": "BOOKED"},
        )

        self.assertRedirects(response, f"/station/{self.station.pk}/appointments/")
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "DONE")

    def test_model_rejects_terminal_status_reopening(self):
        appointment = self.make_appointment(status="DONE")
        appointment.status = "BOOKED"

        with self.assertRaisesMessage(
            ValidationError,
            "Недопустимый переход статуса: DONE → BOOKED",
        ):
            appointment.save()

    def test_truck_duration_is_recomputed_when_appointment_is_edited(self):
        appointment = self.make_appointment(car=self.truck)
        self.assertEqual(appointment.end - appointment.start, timedelta(minutes=60))

        new_start = timezone.make_aware(timezone.datetime(2099, 2, 3, 11, 0))
        appointment.start = new_start
        appointment.end = new_start + timedelta(minutes=30)
        appointment.save()
        appointment.refresh_from_db()

        self.assertEqual(appointment.start, new_start)
        self.assertEqual(appointment.end - appointment.start, timedelta(minutes=60))

    def test_truck_edit_rejects_slot_block_overlap(self):
        from booking.models import SlotBlock

        appointment = self.make_appointment(car=self.truck)
        block_start = timezone.make_aware(timezone.datetime(2099, 2, 3, 11, 30))
        SlotBlock.objects.create(
            station=self.station,
            start=block_start,
            end=block_start + timedelta(minutes=30),
        )

        appointment.start = timezone.make_aware(timezone.datetime(2099, 2, 3, 11, 0))
        appointment.end = appointment.start + timedelta(minutes=30)

        with self.assertRaisesMessage(ValidationError, "Выбранное время заблокировано станцией"):
            appointment.save()
