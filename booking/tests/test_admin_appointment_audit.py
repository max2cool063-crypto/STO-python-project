from datetime import date, time

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.utils import timezone

import booking.admin_safety  # noqa: F401 - ensure safety registrations are applied
from booking.models import (
    Appointment,
    AppointmentLog,
    Brand,
    Car,
    CarModel,
    Station,
    StationSchedule,
)


class AdminAppointmentAuditTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="audit-root@example.com",
            email="audit-root@example.com",
            password="Admin-password-123!",
        )
        self.client_user = User.objects.create_user(
            username="audit-client@example.com",
            password="Client-password-123!",
        )
        self.station = Station.objects.create(name="Audit station")
        target = date(2099, 2, 3)
        StationSchedule.objects.create(
            station=self.station,
            date=target,
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        brand = Brand.objects.create(name="Audit brand")
        car_model = CarModel.objects.create(
            brand=brand,
            name="Audit model",
            vehicle_type="CAR",
        )
        car = Car.objects.create(
            owner=self.client_user,
            model=car_model,
            plate_number="A111AA",
        )
        start = timezone.make_aware(timezone.datetime(2099, 2, 3, 10, 0))
        self.appointment = Appointment.objects.create(
            station=self.station,
            user=self.client_user,
            car=car,
            start=start,
            end=start,
            name="Audit client",
            phone="+79990000000",
        )
        self.model_admin = admin.site._registry[Appointment]
        request = RequestFactory().post("/admin/booking/appointment/1/change/")
        request.user = self.superuser
        self.request = request

    def test_admin_status_change_creates_exactly_one_audit_log(self):
        self.appointment.status = "CANCELLED"

        self.model_admin.save_model(
            self.request,
            self.appointment,
            form=None,
            change=True,
        )

        logs = AppointmentLog.objects.filter(appointment=self.appointment)
        self.assertEqual(logs.count(), 1)
        log = logs.get()
        self.assertEqual(log.changed_by, self.superuser)
        self.assertEqual(log.old_status, "BOOKED")
        self.assertEqual(log.new_status, "CANCELLED")
        self.assertEqual(log.comment, "Изменено через Django Admin")

    def test_admin_non_status_change_does_not_create_status_log(self):
        self.appointment.notes = "Техническая корректировка"

        self.model_admin.save_model(
            self.request,
            self.appointment,
            form=None,
            change=True,
        )

        self.assertFalse(
            AppointmentLog.objects.filter(appointment=self.appointment).exists()
        )

    def test_admin_cannot_bypass_terminal_status_transition_rules(self):
        self.appointment.status = "DONE"
        self.model_admin.save_model(
            self.request,
            self.appointment,
            form=None,
            change=True,
        )
        self.assertEqual(
            AppointmentLog.objects.filter(appointment=self.appointment).count(),
            1,
        )

        self.appointment.status = "BOOKED"
        with self.assertRaises(ValidationError):
            self.model_admin.save_model(
                self.request,
                self.appointment,
                form=None,
                change=True,
            )

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "DONE")
        self.assertEqual(
            AppointmentLog.objects.filter(appointment=self.appointment).count(),
            1,
        )
