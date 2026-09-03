from datetime import date, datetime, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import Appointment, Brand, Car, CarModel, Station, StationStaff, StationWeeklySchedule


class StationCalendarTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="calendar-owner",
            password="Strong-owner-123!",
        )
        self.station = Station.objects.create(name="Calendar Station", slot_duration=30)
        StationStaff.objects.create(
            station=self.station,
            user=self.owner,
            role=StationStaff.ROLE_OWNER,
            is_active=True,
        )
        self.selected_date = date(2099, 2, 3)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=self.selected_date.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        brand = Brand.objects.create(name="GAZ")
        model = CarModel.objects.create(
            brand=brand,
            name="Газон Next",
            vehicle_type="TRUCK",
        )
        self.client_user = User.objects.create_user(username="calendar-client")
        self.car = Car.objects.create(
            owner=self.client_user,
            model=model,
            plate_number="А123АА63",
        )
        self.client.login(username="calendar-owner", password="Strong-owner-123!")

    def test_truck_appointment_is_one_visual_calendar_block(self):
        start = timezone.make_aware(datetime(2099, 2, 3, 11, 0))
        end = timezone.make_aware(datetime(2099, 2, 3, 12, 0))
        appointment = Appointment.objects.create(
            station=self.station,
            user=self.client_user,
            car=self.car,
            start=start,
            end=end,
            name="Васин Илья",
            phone="+79991234567",
        )

        response = self.client.get(
            reverse("station_calendar", kwargs={"station_id": self.station.pk}),
            {"date": self.selected_date.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        physical_slots = response.context["slots"]
        calendar_slots = response.context["calendar_slots"]
        appointment_slots = [slot for slot in physical_slots if slot["appointment"] == appointment]
        visual_appointment_slots = [slot for slot in calendar_slots if slot["appointment"] == appointment]

        self.assertEqual(len(appointment_slots), 2)
        self.assertEqual(len(visual_appointment_slots), 1)
        self.assertEqual(visual_appointment_slots[0]["start"], start)
        self.assertEqual(visual_appointment_slots[0]["end"], end)
        self.assertEqual(response.context["summary"]["appointments"], 1)
