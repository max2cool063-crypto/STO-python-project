from datetime import date, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import (
    Appointment,
    AppointmentLog,
    Brand,
    Car,
    CarModel,
    Station,
    StationStaff,
    StationWeeklySchedule,
)


class AwaitingResultWorkflowTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(
            username="result-operator",
            password="Strong-password-123!",
        )
        self.client_user = User.objects.create_user(username="result-client")
        self.station = Station.objects.create(name="Result Station")
        StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        self.brand = Brand.objects.create(name="Result Brand")
        self.model = CarModel.objects.create(
            brand=self.brand,
            name="Result Model",
            vehicle_type="CAR",
        )
        self.car = Car.objects.create(
            owner=self.client_user,
            model=self.model,
            plate_number="А777АА77",
        )
        target = date(2099, 4, 5)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=target.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        start = timezone.make_aware(timezone.datetime(2099, 4, 5, 10, 0))
        self.appointment = Appointment.objects.create(
            station=self.station,
            user=self.client_user,
            car=self.car,
            start=start,
            end=start,
            name="Клиент",
        )
        self.url = reverse(
            "station_appointment_status",
            args=[self.station.pk, self.appointment.pk],
        )
        self.client.force_login(self.operator)

    def test_operator_cannot_set_system_managed_awaiting_result_status(self):
        response = self.client.post(
            self.url,
            {"status": "AWAITING_RESULT", "comment": "manual"},
        )

        self.assertEqual(response.status_code, 302)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "BOOKED")
        self.assertFalse(
            AppointmentLog.objects.filter(appointment=self.appointment).exists()
        )

    def test_operator_can_finalize_awaiting_result_as_done(self):
        Appointment.objects.filter(pk=self.appointment.pk).update(
            status="AWAITING_RESULT"
        )

        response = self.client.post(
            self.url,
            {"status": "DONE", "comment": "ТО выполнено"},
        )

        self.assertEqual(response.status_code, 302)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "DONE")
        log = AppointmentLog.objects.get(appointment=self.appointment)
        self.assertEqual(log.old_status, "AWAITING_RESULT")
        self.assertEqual(log.new_status, "DONE")
        self.assertEqual(log.changed_by, self.operator)
        self.assertEqual(log.comment, "ТО выполнено")

    def test_operator_can_finalize_awaiting_result_as_no_show(self):
        Appointment.objects.filter(pk=self.appointment.pk).update(
            status="AWAITING_RESULT"
        )

        response = self.client.post(
            self.url,
            {"status": "NO_SHOW", "comment": "Клиент не приехал"},
        )

        self.assertEqual(response.status_code, 302)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "NO_SHOW")
        self.assertTrue(
            AppointmentLog.objects.filter(
                appointment=self.appointment,
                old_status="AWAITING_RESULT",
                new_status="NO_SHOW",
                changed_by=self.operator,
            ).exists()
        )
