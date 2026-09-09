"""Sentinel data for the disposable smoke deployment only."""
from datetime import datetime, time, timedelta
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import Client
from django.utils import timezone
from PIL import Image

from booking.models import Appointment, AppointmentPhoto, Brand, Car, CarModel, EmailOutbox, Station, StationSchedule
from booking.email_queue import enqueue_mail

USERNAME = "ci-restore-sentinel"


def photo_bytes():
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "blue").save(buffer, format="PNG")
    return buffer.getvalue()


def seed():
    user = User.objects.create_user(username=USERNAME)
    station = Station.objects.create(name="Restore sentinel station")
    model = CarModel.objects.create(brand=Brand.objects.create(name="Restore brand"), name="Restore car", vehicle_type="CAR")
    car = Car.objects.create(owner=user, model=model, plate_number="А123АА77")
    start = timezone.make_aware(datetime(2099, 3, 3, 10))
    StationSchedule.objects.create(station=station, date=start.date(), work_start=time(9), work_end=time(18))
    appointment = Appointment.objects.create(user=user, station=station, car=car, start=start, end=start, name="Restore client")
    AppointmentPhoto.objects.create(appointment=appointment, image=ContentFile(photo_bytes(), name="restore-sentinel.png"))
    enqueue_mail("Restore queue sentinel", "original queued body", None,
        ["sentinel@example.com"], event_key="restore-outbox")
    EmailOutbox.objects.filter(subject="Restore queue sentinel").update(available_at=timezone.now() + timedelta(days=1))


def mutate():
    EmailOutbox.objects.filter(subject="Restore queue sentinel").delete()
    photo = AppointmentPhoto.objects.get(appointment__user__username=USERNAME)
    with open(photo.image.path, "wb") as output:
        output.write(b"mutated")
    Appointment.objects.filter(user__username=USERNAME).delete()
    User.objects.get(username=USERNAME).delete()


def verify():
    queued = EmailOutbox.objects.get(subject="Restore queue sentinel")
    assert queued.body == "original queued body" and queued.status == "pending"
    user = User.objects.get(username=USERNAME)
    appointment = Appointment.objects.get(user=user)
    assert appointment.status == "BOOKED"
    assert appointment.car.plate_number == "А123АА77"
    photo = appointment.photos.get()
    with photo.image.open("rb") as restored:
        assert restored.read() == photo_bytes(), "Restored image bytes do not match"
    client = Client()
    anonymous = client.get(photo.image.url, HTTP_HOST="localhost")
    assert anonymous.status_code in (302, 403), anonymous.status_code
    client.force_login(user)
    response = client.get(photo.image.url, HTTP_HOST="localhost")
    assert response.status_code == 200, response.status_code
    try:
        assert b"".join(response.streaming_content) == photo_bytes()
    finally:
        response.close()
