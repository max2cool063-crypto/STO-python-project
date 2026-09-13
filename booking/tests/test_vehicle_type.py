from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from booking.models import Appointment, Brand, Car, CarModel, Station, StationStaff, StationWeeklySchedule


class VehicleTypeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="vehicle-client")
        self.operator = User.objects.create_user(username="vehicle-operator")
        self.station = Station.objects.create(name="Vehicle station")
        self.role = StationStaff.objects.create(user=self.operator, station=self.station, role="OPERATOR")
        self.model = CarModel.objects.create(brand=Brand.objects.create(name="VW"), name="Caddy")
        self.car = Car.objects.create(owner=self.user, model=self.model, plate_number="А123ВС77", vehicle_type="CAR")
        self.truck = Car.objects.create(owner=self.user, model=self.model, plate_number="В234СЕ77", vehicle_type="TRUCK")
        self.day = date(2099, 2, 3)
        StationWeeklySchedule.objects.create(station=self.station, weekday=self.day.weekday(), work_start=time(9), work_end=time(18))
        self.start = self.station.make_local_datetime(self.day, time(10))
        self.appointment = self.book(self.car, self.start)

    def book(self, car, start):
        return Appointment.objects.create(car=car, user=car.owner, station=self.station, start=start, end=start, name="Клиент")

    def edit_url(self, car=None):
        return reverse("station_car_edit", args=[self.station.pk, (car or self.car).pk])

    def test_same_model_has_independent_types_and_durations(self):
        truck_visit = self.book(self.truck, self.start + timedelta(hours=2))
        self.assertEqual(self.appointment.duration_minutes, 30)
        self.assertEqual(truck_visit.duration_minutes, 60)
        self.client.force_login(self.user)
        for car, minutes in [(self.car, 30), (self.truck, 60)]:
            slots = self.client.get(reverse("station_slots_api", args=[self.station.pk]), {"date": self.day.isoformat(), "car": car.pk}).json()["slots"]
            from datetime import datetime
            self.assertEqual((datetime.fromisoformat(slots[0]["end"]) - datetime.fromisoformat(slots[0]["start"])).total_seconds(), minutes * 60)

    def test_operator_edits_known_car_but_not_owner_or_model(self):
        self.client.force_login(self.operator)
        response = self.client.post(self.edit_url(), {"plate_number": self.car.plate_number, "vin": "", "vehicle_type": "TRUCK", "owner": self.operator.pk, "model": 9999})
        self.assertRedirects(response, reverse("station_clients", args=[self.station.pk]))
        self.car.refresh_from_db()
        self.assertEqual(self.car.vehicle_type, "TRUCK")
        self.assertEqual(self.car.owner_id, self.user.pk)
        self.assertEqual(self.car.model_id, self.model.pk)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.duration_minutes, 30)

    def test_owner_can_edit_and_invalid_type_is_rejected(self):
        owner = User.objects.create_user(username="vehicle-owner")
        StationStaff.objects.create(user=owner, station=self.station, role="OWNER")
        self.client.force_login(owner)
        self.assertEqual(self.client.get(self.edit_url()).status_code, 200)
        for value in ["", "BUS", "truck"]:
            response = self.client.post(self.edit_url(), {"plate_number": self.car.plate_number, "vehicle_type": value}, HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 400)
        self.car.refresh_from_db()
        self.assertEqual(self.car.vehicle_type, "CAR")

    def test_unrelated_car_of_known_client_is_not_accessible(self):
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(self.edit_url(self.truck)).status_code, 404)
        self.assertEqual(self.client.post(self.edit_url(self.truck), {"vehicle_type": "CAR"}).status_code, 404)
        response = self.client.get(reverse("station_clients", args=[self.station.pk]))
        self.assertContains(response, self.edit_url())
        self.assertNotContains(response, self.edit_url(self.truck))

    def test_client_and_other_station_staff_cannot_edit(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.edit_url()).status_code, 302)
        other = User.objects.create_user(username="other-station-operator")
        StationStaff.objects.create(user=other, station=Station.objects.create(name="Other"), role="OPERATOR")
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.edit_url(), {"vehicle_type": "TRUCK"}).status_code, 302)
        self.car.refresh_from_db()
        self.assertEqual(self.car.vehicle_type, "CAR")

    def test_type_change_does_not_resize_on_ordinary_save(self):
        self.car.vehicle_type = "TRUCK"
        self.car.save()
        self.appointment.notes = "Заметка"
        self.appointment.save()
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.duration_minutes, 30)

    def test_explicit_recalculation_rejects_overlap(self):
        self.book(self.truck, self.start + timedelta(minutes=30))
        self.car.vehicle_type = "TRUCK"
        self.car.save()
        with self.assertRaises(ValidationError):
            self.appointment.save(recalculate_duration=True)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.duration_minutes, 30)

    def test_station_edit_recalculates_current_type(self):
        self.car.vehicle_type = "TRUCK"
        self.car.save()
        self.client.force_login(self.operator)
        response = self.client.post(reverse("station_appointment_edit", args=[self.station.pk, self.appointment.pk]), {"start": self.start.isoformat(), "notes": ""})
        self.assertEqual(response.status_code, 302)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.duration_minutes, 60)

    def test_client_create_requires_type_and_edit_saves_type(self):
        self.client.force_login(self.user)
        data = {"model": self.model.pk, "plate": "К345МН77"}
        self.client.post(reverse("cabinet_cars"), data)
        self.assertEqual(Car.objects.count(), 2)
        self.client.post(reverse("cabinet_cars"), {**data, "vehicle_type": "TRUCK"})
        self.assertEqual(Car.objects.get(plate_number=data["plate"]).vehicle_type, "TRUCK")
        self.client.post(reverse("cabinet_car_edit", args=[self.car.pk]), {"plate_number": self.car.plate_number, "vehicle_type": "TRUCK"})
        self.car.refresh_from_db()
        self.assertEqual(self.car.vehicle_type, "TRUCK")

    def test_station_new_car_type_is_required_and_used(self):
        self.client.force_login(self.operator)
        url = reverse("station_appointment_create", args=[self.station.pk])
        data = {"new_model_id": self.model.pk, "plate": "К345МН77", "client_name": "Клиент", "start": (self.start + timedelta(hours=3)).isoformat()}
        self.client.post(url, data)
        self.assertEqual(Car.objects.count(), 2)
        self.client.post(url, {**data, "vehicle_type": "TRUCK"})
        visit = Appointment.objects.get(car__plate_number=data["plate"])
        self.assertEqual(visit.car.vehicle_type, "TRUCK")
        self.assertEqual(visit.duration_minutes, 60)


class CarCatalogFixtureTests(TestCase):
    def test_initial_catalog_loads_twice_and_sequences_allow_new_entries(self):
        for _ in range(2):
            call_command("loaddata", "cars", verbosity=0)
        self.assertEqual(Brand.objects.count(), 84)
        self.assertEqual(CarModel.objects.count(), 714)
        brand = Brand.objects.create(name="New catalog brand")
        CarModel.objects.create(brand=brand, name="New catalog model")
        self.assertEqual(CarModel.objects.count(), 715)
