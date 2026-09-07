from datetime import date, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import Appointment, Brand, Car, CarModel, Station, StationStaff, StationWeeklySchedule


class TerminalAppointmentEditTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="terminal-owner@example.com",
            password="test-password",
        )
        client_user = User.objects.create_user(
            username="terminal-client@example.com",
            password="test-password",
        )
        station = Station.objects.create(name="Terminal Station")
        StationStaff.objects.create(
            station=station,
            user=self.owner,
            role=StationStaff.ROLE_OWNER,
            is_active=True,
        )
        target = date(2099, 2, 3)
        StationWeeklySchedule.objects.create(
            station=station,
            weekday=target.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        brand = Brand.objects.create(name="Terminal Test")
        model = CarModel.objects.create(brand=brand, name="Passenger", vehicle_type="CAR")
        car = Car.objects.create(owner=client_user, model=model, plate_number="A111AA")
        start = timezone.make_aware(timezone.datetime(2099, 2, 3, 10, 0))
        self.appointment = Appointment.objects.create(
            station=station,
            user=client_user,
            car=car,
            start=start,
            end=start + timezone.timedelta(minutes=30),
            name="Client",
        )
        self.appointment.status = "DONE"
        self.appointment.save()
        self.station = station
        self.client.login(username="terminal-owner@example.com", password="test-password")

    def test_terminal_appointment_cannot_be_moved_or_notes_changed(self):
        url = reverse(
            "station_appointment_edit",
            kwargs={"station_id": self.station.pk, "pk": self.appointment.pk},
        )
        new_start = timezone.make_aware(timezone.datetime(2099, 2, 3, 11, 0))

        response = self.client.post(
            url,
            {"start": new_start.isoformat(), "notes": "Should not be saved"},
        )

        self.assertRedirects(
            response,
            reverse(
                "station_appointment_detail",
                kwargs={"station_id": self.station.pk, "pk": self.appointment.pk},
            ),
        )
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "DONE")
        self.assertEqual(self.appointment.local_start.hour, 10)
        self.assertEqual(self.appointment.notes, "")
