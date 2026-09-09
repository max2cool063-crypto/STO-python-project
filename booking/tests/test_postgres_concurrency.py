from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from threading import Barrier
from time import monotonic, sleep
from unittest import skipUnless
from uuid import uuid4

from django.contrib.auth.models import User
from django.db import connection, connections, transaction
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from booking.models import Appointment, AppointmentLog, Brand, Car, CarModel, SlotBlock, Station, StationSchedule, StationStaff


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL row locks")
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class BookingConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.station = Station.objects.create(name="Concurrent station")
        self.owner = User.objects.create_user(username="concurrent-owner")
        StationStaff.objects.create(station=self.station, user=self.owner, role=StationStaff.ROLE_OWNER)
        self.users = [User.objects.create_user(username=f"concurrent-client-{i}") for i in range(2)]
        brand = Brand.objects.create(name="Concurrency brand")
        model = CarModel.objects.create(brand=brand, name="Car", vehicle_type="CAR")
        self.cars = [Car.objects.create(owner=user, model=model, plate_number=f"А11{i}АА77") for i, user in enumerate(self.users)]
        self.start = timezone.make_aware(datetime(2099, 3, 3, 10))
        StationSchedule.objects.create(station=self.station, date=self.start.date(), work_start=time(9), work_end=time(18))

    def race(self, locked_queryset, requests):
        """Hold a row until BOTH independent HTTP requests are waiting in PostgreSQL."""
        gate = Barrier(3)
        token = f"sto-race-{uuid4().hex}"

        def worker(index, user, url, data):
            try:
                client = Client()
                client.force_login(user)
                with connection.cursor() as cursor:
                    cursor.execute("SET application_name = %s", [f"{token}-{index}"])
                    cursor.execute("SET lock_timeout = '30s'")
                    cursor.execute("SET statement_timeout = '45s'")
                gate.wait(timeout=20)
                return client.post(url, data).status_code
            finally:
                connections.close_all()

        with self.assertNoLogs("booking", level="ERROR"), ThreadPoolExecutor(max_workers=2) as pool:
            with transaction.atomic():
                list(locked_queryset.select_for_update())
                futures = [pool.submit(worker, i, *request) for i, request in enumerate(requests)]
                gate.wait(timeout=20)
                deadline = monotonic() + 15
                while monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_stat_clear_snapshot()")
                        cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE application_name LIKE %s AND wait_event_type = 'Lock'", [token + "%"])
                        if cursor.fetchone()[0] == 2:
                            break
                    sleep(0.02)
                else:
                    self.fail("Both requests did not contend for the held PostgreSQL lock")
            statuses = [future.result(timeout=50) for future in futures]
        self.assertEqual(statuses, [302, 302])

    def test_two_clients_cannot_commit_the_same_slot(self):
        url = reverse("book_station", kwargs={"pk": self.station.pk})
        requests = [(user, url, {"start": self.start.isoformat(), "car": car.pk}) for user, car in zip(self.users, self.cars)]
        self.race(Station.objects.filter(pk=self.station.pk), requests)
        self.assertEqual(Appointment.objects.filter(station=self.station).count(), 1)

    def test_booking_and_slot_block_cannot_both_commit(self):
        requests = [
            (self.users[0], reverse("book_station", kwargs={"pk": self.station.pk}), {"start": self.start.isoformat(), "car": self.cars[0].pk}),
            (self.owner, reverse("station_slot_blocks", kwargs={"station_id": self.station.pk}), {"action": "add", "start": self.start.isoformat(), "end": (self.start + timedelta(minutes=30)).isoformat()}),
        ]
        self.race(Station.objects.filter(pk=self.station.pk), requests)
        self.assertEqual(Appointment.objects.count() + SlotBlock.objects.count(), 1)

    def test_reschedule_cannot_reopen_a_concurrently_cancelled_appointment(self):
        appointment = Appointment.objects.create(station=self.station, user=self.users[0], car=self.cars[0], start=self.start, end=self.start, name="Client")
        requests = [
            (self.owner, reverse("station_appointment_edit", kwargs={"station_id": self.station.pk, "pk": appointment.pk}), {"start": (self.start + timedelta(hours=1)).isoformat()}),
            (self.users[0], reverse("cabinet_cancel_appointment", kwargs={"pk": appointment.pk}), {}),
        ]
        self.race(Appointment.objects.filter(pk=appointment.pk), requests)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "CANCELLED")
        self.assertIn(appointment.start, (self.start, self.start + timedelta(hours=1)))
        self.assertEqual(AppointmentLog.objects.filter(appointment=appointment, new_status="CANCELLED").count(), 1)
