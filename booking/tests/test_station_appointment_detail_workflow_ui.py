from datetime import datetime, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import (
    Appointment,
    Brand,
    Car,
    CarModel,
    Station,
    StationStaff,
    StationWeeklySchedule,
)


class StationAppointmentDetailWorkflowUiTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(
            username="detail-operator@example.com",
            password="test-password",
        )
        self.client_user = User.objects.create_user(
            username="detail-client@example.com",
            password="test-password",
        )
        self.station = Station.objects.create(name="Detail station")
        StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        brand = Brand.objects.create(name="Detail brand")
        model = CarModel.objects.create(
            brand=brand,
            name="Detail model",
            vehicle_type="CAR",
        )
        car = Car.objects.create(
            owner=self.client_user,
            model=model,
            plate_number="А123ВС77",
        )
        start = timezone.make_aware(datetime(2099, 1, 5, 10, 0))
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=start.date().weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        self.appointment = Appointment.objects.create(
            station=self.station,
            user=self.client_user,
            car=car,
            start=start,
            end=start,
            name="Client",
        )
        self.client.login(
            username="detail-operator@example.com",
            password="test-password",
        )

    def _detail(self):
        return self.client.get(
            reverse(
                "station_appointment_detail",
                kwargs={"station_id": self.station.pk, "pk": self.appointment.pk},
            )
        )

    def test_booked_record_exposes_edit_photo_and_status_actions(self):
        response = self._detail()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Редактировать")
        self.assertContains(response, "Добавить фото")
        self.assertContains(response, "Сохранить статус")

    def test_awaiting_result_only_exposes_finalization_actions(self):
        self.appointment.status = "AWAITING_RESULT"
        self.appointment.save(update_fields=["status"])

        response = self._detail()

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Редактировать")
        self.assertNotContains(response, "Добавить фото")
        self.assertContains(response, "Сохранить статус")
        self.assertContains(response, "Выполнено")
        self.assertContains(response, "Не приехал")

    def test_terminal_record_is_read_only_in_detail_ui(self):
        self.appointment.status = "DONE"
        self.appointment.save(update_fields=["status"])

        response = self._detail()

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Редактировать")
        self.assertNotContains(response, "Добавить фото")
        self.assertNotContains(response, "Сохранить статус")
        self.assertContains(response, "Дальнейшее изменение статуса недоступно")
