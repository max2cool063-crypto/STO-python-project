from datetime import date, datetime, time, timedelta
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from booking.models import Appointment, Brand, Car, CarModel, Station, StationStaff, StationWeeklySchedule


class StationAppointmentWorkflowTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(username="operator-workflow", password="test-password")
        self.station = Station.objects.create(name="Station Workflow")
        StationStaff.objects.create(station=self.station, user=self.operator, role=StationStaff.ROLE_OPERATOR, is_active=True)
        self.brand = Brand.objects.create(name="Test Brand")
        self.model = CarModel.objects.create(brand=self.brand, name="Test Model", vehicle_type="CAR")
        target = date(2099, 2, 3)
        StationWeeklySchedule.objects.create(station=self.station, weekday=target.weekday(), work_start=time(9, 0), work_end=time(18, 0))
        self.start = "2099-02-03T10:00:00+03:00"
        self.start_dt = timezone.make_aware(datetime(2099, 2, 3, 10, 0))
        self.client.login(username="operator-workflow", password="test-password")

    @staticmethod
    def image_upload(name="car.jpg"):
        buffer = BytesIO()
        Image.new("RGB", (20, 20), "white").save(buffer, format="JPEG")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")

    def test_operator_can_create_client_without_email_and_attach_photo(self):
        response = self.client.post(
            reverse("station_appointment_create", kwargs={"station_id": self.station.id}),
            {"plate": "А123АА77", "new_model_id": self.model.id, "new_user_email": "", "client_name": "Иванов Иван", "client_phone": "+79990000000", "start": self.start, "photos": self.image_upload()},
        )
        self.assertRedirects(response, reverse("station_appointments", kwargs={"station_id": self.station.id}))
        appointment = Appointment.objects.get(station=self.station)
        self.assertEqual(appointment.name, "Иванов Иван")
        self.assertEqual(appointment.phone, "+79990000000")
        self.assertEqual(appointment.user.email, "")
        self.assertEqual(appointment.photos.count(), 1)

    def test_operator_can_create_new_car_with_vin(self):
        response = self.client.post(
            reverse("station_appointment_create", kwargs={"station_id": self.station.id}),
            {
                "plate": "В456ВВ63",
                "new_model_id": self.model.id,
                "vin": "XTA12345678901234",
                "new_user_email": "",
                "client_name": "Петров Пётр",
                "client_phone": "+79991112233",
                "start": self.start,
            },
        )
        self.assertRedirects(response, reverse("station_appointments", kwargs={"station_id": self.station.id}))
        appointment = Appointment.objects.get(station=self.station)
        self.assertEqual(appointment.car.vin, "XTA12345678901234")
        self.assertEqual(appointment.vin, "XTA12345678901234")

    def test_operator_can_load_slots_for_saved_client_car(self):
        client_user = User.objects.create_user(username="saved-client-workflow", email="saved@example.com")
        car = Car.objects.create(owner=client_user, model=self.model, plate_number="С963УК763")
        previous_day = date(2099, 2, 2)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=previous_day.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        Appointment.objects.create(
            station=self.station,
            user=client_user,
            car=car,
            start=timezone.make_aware(datetime(2099, 2, 2, 10, 0)),
            end=timezone.make_aware(datetime(2099, 2, 2, 10, 30)),
            name="Клиент",
        )

        response = self.client.get(
            reverse("station_slots_api", kwargs={"station_id": self.station.id}),
            {"date": "2099-02-03", "car": car.id},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["slots"]), 18)
        self.assertEqual(data["slots"][0]["start"][:16], "2099-02-03T09:00")

    def test_operator_uses_canonical_identity_of_selected_saved_car(self):
        previous_owner = User.objects.create_user(
            username="selected-owner",
            first_name="Иван",
            last_name="Иванов",
        )
        car = Car.objects.create(
            owner=previous_owner,
            model=self.model,
            plate_number="С963УК763",
            vin="XTA210990Y1234567",
        )
        Appointment.objects.create(
            station=self.station,
            user=previous_owner,
            car=car,
            start=self.start_dt,
            end=self.start_dt + timedelta(minutes=30),
            name="Иванов Иван",
        )

        response = self.client.post(
            reverse("station_appointment_create", kwargs={"station_id": self.station.id}),
            {
                "car_id": car.id,
                "client_name": "Петров Пётр",
                "client_phone": "+79992223344",
                "new_user_email": "new@example.com",
                "start": self.start,
            },
        )

        self.assertRedirects(response, reverse("station_appointments", kwargs={"station_id": self.station.id}))
        appointments = list(Appointment.objects.filter(station=self.station).order_by("id"))
        self.assertEqual(len(appointments), 2)
        appointment = appointments[-1]
        previous_owner.refresh_from_db()
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(appointment.user_id, previous_owner.pk)
        self.assertEqual(appointment.car_id, car.pk)
        self.assertEqual(appointment.name, "Иванов Иван")
        self.assertEqual(appointment.phone, "")
        self.assertEqual(previous_owner.first_name, "Иван")
        self.assertEqual(previous_owner.last_name, "Иванов")

    def test_station_detail_and_edit_are_available_to_operator(self):
        user = User.objects.create_user(username="client-workflow", email="client@example.com")
        car = Car.objects.create(owner=user, model=self.model, plate_number="B456BB")
        appointment = Appointment.objects.create(
            station=self.station,
            user=user,
            car=car,
            start=self.start_dt,
            end=self.start_dt,
            name="Клиент",
        )
        detail = self.client.get(reverse("station_appointment_detail", kwargs={"station_id": self.station.id, "pk": appointment.id}))
        self.assertEqual(detail.status_code, 200)
        edit = self.client.get(reverse("station_appointment_edit", kwargs={"station_id": self.station.id, "pk": appointment.id}))
        self.assertEqual(edit.status_code, 200)
