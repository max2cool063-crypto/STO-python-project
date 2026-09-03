from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from booking.timezones import detect_timezone, get_timezone, make_station_datetime, station_localtime


# =========================
# СТАНЦИЯ ТО
# =========================

class Station(models.Model):
    name = models.CharField("Название станции ТО", max_length=255)
    address = models.CharField("Адрес", max_length=255, blank=True)
    rsa_id = models.CharField("ID из реестра РСА (№ ОТО)", max_length=20, blank=True, null=True, db_index=True, unique=True)
    latitude = models.FloatField("Широта", null=True, blank=True)
    longitude = models.FloatField("Долгота", null=True, blank=True)
    timezone = models.CharField("Часовой пояс", max_length=64, blank=True, default="")
    phone = models.CharField("Телефон", max_length=50, blank=True, default="")
    email = models.EmailField("Email", blank=True, default="")

    slot_duration = models.PositiveIntegerField("Длительность базового слота (мин)", default=30)
    is_active = models.BooleanField("Активна для записи", default=True)

    class Meta:
        verbose_name = "Станция ТО"
        verbose_name_plural = "Станции ТО"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.timezone and self.latitude is not None and self.longitude is not None:
            self.timezone = detect_timezone(self.latitude, self.longitude) or ""
        super().save(*args, **kwargs)

    def get_timezone(self):
        return get_timezone(self.timezone)

    def local_now(self):
        return station_localtime(self)

    def local_date(self):
        return self.local_now().date()

    def make_local_datetime(self, value_date, value_time):
        return make_station_datetime(self, value_date, value_time)

    def get_working_hours(self, date):
        schedule = self.schedules.filter(date=date).first()
        if schedule:
            return schedule.work_start, schedule.work_end

        import holidays as holidays_lib
        if date in holidays_lib.Russia(years=date.year):
            return None, None

        weekday = date.weekday()
        weekly = self.weekly_schedules.filter(weekday=weekday).first()
        if weekly:
            return weekly.work_start, weekly.work_end

        return None, None

    def get_available_slots(self, date, vehicle_type=None):
        work_start, work_end = self.get_working_hours(date)
        if not work_start or not work_end or work_start >= work_end:
            return []

        slot_mins = self.slot_duration
        required_mins = slot_mins * 2 if vehicle_type == "TRUCK" else slot_mins

        start_dt = self.make_local_datetime(date, work_start)
        end_dt = self.make_local_datetime(date, work_end)
        current_time = self.local_now()

        appointments = list(
            Appointment.objects.filter(
                station=self,
                start__lt=end_dt,
                end__gt=start_dt,
            ).exclude(status="CANCELLED").only("start", "end")
        )
        blocks = list(
            SlotBlock.objects.filter(
                station=self,
                start__lt=end_dt,
                end__gt=start_dt,
            ).only("start", "end")
        )

        slots = []
        while start_dt + timedelta(minutes=required_mins) <= end_dt:
            slot_end = start_dt + timedelta(minutes=required_mins)
            has_conflict = any(
                appointment.start < slot_end and appointment.end > start_dt
                for appointment in appointments
            )
            is_blocked = any(
                block.start < slot_end and block.end > start_dt
                for block in blocks
            )

            if not has_conflict and not is_blocked and start_dt > current_time:
                slots.append({"start": start_dt.isoformat(), "end": slot_end.isoformat()})

            start_dt += timedelta(minutes=slot_mins)

        return slots


# =========================
# НЕДЕЛЬНЫЙ ГРАФИК
# =========================

class StationWeeklySchedule(models.Model):
    WEEKDAYS = [
        (0, "Понедельник"), (1, "Вторник"), (2, "Среда"), (3, "Четверг"),
        (4, "Пятница"), (5, "Суббота"), (6, "Воскресенье"),
    ]
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="weekly_schedules", verbose_name="Станция")
    weekday = models.IntegerField("День недели", choices=WEEKDAYS)
    work_start = models.TimeField("Начало работы")
    work_end = models.TimeField("Конец работы")

    class Meta:
        unique_together = ("station", "weekday")
        ordering = ["weekday"]
        verbose_name = "Недельный график станции"
        verbose_name_plural = "Недельные графики станций"

    def __str__(self):
        return f"{self.station} — {self.get_weekday_display()}"


class StationSchedule(models.Model):
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="schedules", verbose_name="Станция")
    date = models.DateField("Дата")
    work_start = models.TimeField("Начало работы")
    work_end = models.TimeField("Конец работы")

    class Meta:
        unique_together = ("station", "date")
        ordering = ["date"]
        verbose_name = "График работы станции"
        verbose_name_plural = "Графики работы станций"

    def __str__(self):
        return f"{self.station} — {self.date}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField("Телефон", max_length=30, blank=True)

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self):
        return self.user.username


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Марка"
        verbose_name_plural = "Марки"
        ordering = ["name"]

    def __str__(self):
        return self.name


class CarModel(models.Model):
    VEHICLE_TYPES = [("CAR", "Легковой"), ("TRUCK", "Грузовой")]
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="models")
    name = models.CharField(max_length=100)
    vehicle_type = models.CharField("Тип ТС", max_length=10, choices=VEHICLE_TYPES, default="CAR")

    class Meta:
        unique_together = ("brand", "name")
        verbose_name = "Модель"
        verbose_name_plural = "Модели"

    def __str__(self):
        return f"{self.brand} {self.name}"


class Car(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    model = models.ForeignKey(CarModel, on_delete=models.CASCADE)
    plate_number = models.CharField("Госномер", max_length=20)
    vin = models.CharField(max_length=32, blank=True, null=True)
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    def save(self, *args, **kwargs):
        if self.plate_number:
            self.plate_number = self.plate_number.upper()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Автомобиль"
        verbose_name_plural = "Автомобили"

    def __str__(self):
        return f"{self.model.brand.name} {self.model.name} ({self.plate_number})"


class Appointment(models.Model):
    STATUS_CHOICES = [
        ("BOOKED", "Запланировано"), ("CANCELLED", "Отменено"),
        ("DONE", "Выполнено"), ("NO_SHOW", "Не приехал"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="appointments", verbose_name="Пользователь")
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name="appointments", verbose_name="Автомобиль")
    station = models.ForeignKey(Station, on_delete=models.CASCADE, verbose_name="Станция")
    start = models.DateTimeField("Начало")
    end = models.DateTimeField("Конец")
    name = models.CharField("Имя клиента", max_length=100)
    phone = models.CharField("Телефон", max_length=20, blank=True, null=True)
    vin = models.CharField("VIN", max_length=32, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="BOOKED", verbose_name="Статус")
    notes = models.TextField("Комментарий оператора", blank=True, default="")

    class Meta:
        ordering = ["start"]
        verbose_name = "Запись на ТО"
        verbose_name_plural = "Записи на ТО"
        indexes = [models.Index(fields=["station", "start", "end"]), models.Index(fields=["user", "start"])]

    def __str__(self):
        return f"{self.station} — {station_localtime(self.station, self.start):%d.%m %H:%M}"

    def get_required_duration(self):
        base = timedelta(minutes=self.station.slot_duration)
        return base * 2 if self.car.model.vehicle_type == "TRUCK" else base

    def clean(self):
        if self.start >= self.end:
            raise ValidationError("Время окончания должно быть позже начала")

        local_start = station_localtime(self.station, self.start)
        local_end = station_localtime(self.station, self.end)
        date = local_start.date()
        work_start, work_end = self.station.get_working_hours(date)
        if not work_start or not work_end:
            raise ValidationError("Станция не работает в этот день")
        if not (work_start <= local_start.time() < work_end):
            raise ValidationError("Запись вне графика работы станции")

        expected_end = self.start + self.get_required_duration()
        expected_end_local = station_localtime(self.station, expected_end)
        if expected_end_local.date() != date or expected_end_local.time() > work_end:
            raise ValidationError(
                f"Запись заканчивается в {expected_end_local.strftime('%H:%M')}, "
                f"станция работает до {work_end.strftime('%H:%M')}"
            )
        conflict = Appointment.objects.filter(
            station=self.station, start__lt=expected_end, end__gt=self.start,
        ).exclude(pk=self.pk).exclude(status="CANCELLED")
        if conflict.exists():
            raise ValidationError("Выбранное время уже занято")

    def save(self, *args, **kwargs):
        if self.status in ("CANCELLED", "DONE", "NO_SHOW"):
            super().save(*args, **kwargs)
            return
        self.end = self.start + self.get_required_duration()
        self.full_clean()
        super().save(*args, **kwargs)


class AppointmentPhoto(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="appointments/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Фото записи"
        verbose_name_plural = "Фото записей"

    def __str__(self):
        return f"Фото #{self.pk} к записи #{self.appointment_id}"


class StationStaff(models.Model):
    ROLE_OWNER = "OWNER"
    ROLE_OPERATOR = "OPERATOR"
    ROLE_CHOICES = [(ROLE_OWNER, "Владелец"), (ROLE_OPERATOR, "Оператор")]
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="staff", verbose_name="Станция")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="station_roles", verbose_name="Пользователь")
    role = models.CharField("Роль", max_length=10, choices=ROLE_CHOICES)
    is_active = models.BooleanField("Активен", default=True)
    receive_notifications = models.BooleanField("Получать уведомления о новых записях", default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_staff", verbose_name="Кто создал")
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        unique_together = ("station", "user")
        verbose_name = "Сотрудник станции"
        verbose_name_plural = "Сотрудники станций"
        indexes = [models.Index(fields=["user", "role", "is_active"])]

    def __str__(self):
        return f"{self.user} — {self.get_role_display()} @ {self.station}"

    def is_owner(self):
        return self.role == self.ROLE_OWNER

    def is_operator(self):
        return self.role == self.ROLE_OPERATOR


class SlotBlock(models.Model):
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="slot_blocks")
    start = models.DateTimeField("Начало блокировки")
    end = models.DateTimeField("Конец блокировки")
    reason = models.CharField("Причина", max_length=255, blank=True, default="")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start"]
        indexes = [models.Index(fields=["station", "start", "end"])]
        verbose_name = "Блокировка слота"
        verbose_name_plural = "Блокировки слотов"

    def __str__(self):
        return f"{self.station} — {station_localtime(self.station, self.start):%d.%m %H:%M}–{station_localtime(self.station, self.end):%H:%M}"

    def clean(self):
        if self.start >= self.end:
            raise ValidationError("Конец блокировки должен быть позже начала")


class AppointmentLog(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name="logs", verbose_name="Запись")
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Кто изменил")
    old_status = models.CharField("Старый статус", max_length=20, blank=True)
    new_status = models.CharField("Новый статус", max_length=20)
    comment = models.TextField("Комментарий", blank=True, default="")
    created_at = models.DateTimeField("Время", auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Запись в журнале"
        verbose_name_plural = "Журнал записей"

    def __str__(self):
        return f"#{self.appointment_id} {self.old_status}→{self.new_status} {station_localtime(self.appointment.station, self.created_at):%d.%m %H:%M}"


class Notification(models.Model):
    TYPE_NEW_APPOINTMENT = "NEW_APPOINTMENT"
    TYPE_CHOICES = [(TYPE_NEW_APPOINTMENT, "Новая запись")]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications", verbose_name="Получатель")
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="notifications", verbose_name="Станция")
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications", verbose_name="Запись")
    notification_type = models.CharField("Тип", max_length=50, choices=TYPE_CHOICES)
    title = models.CharField("Заголовок", max_length=255)
    message = models.TextField("Сообщение")
    is_read = models.BooleanField("Прочитано", default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"]),
            models.Index(fields=["station", "created_at"]),
        ]
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"

    def __str__(self):
        return f"{self.title} — {self.recipient}"
