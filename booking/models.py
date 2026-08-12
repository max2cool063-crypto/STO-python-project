from datetime import datetime, timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.timezone import make_aware, now
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


# =========================
# СТАНЦИЯ ТО
# =========================

class Station(models.Model):
    name = models.CharField("Название станции ТО", max_length=255)
    address = models.CharField("Адрес", max_length=255, blank=True)
    latitude = models.FloatField("Широта", null=True, blank=True)
    longitude = models.FloatField("Долгота", null=True, blank=True)
    phone = models.CharField("Телефон", max_length=50, blank=True, default="")
    email = models.EmailField("Email", blank=True, default="")

    slot_duration = models.PositiveIntegerField(
        "Длительность слота (мин)",
        default=60
    )
    
    is_active = models.BooleanField("Активна для записи", default=True)
    
    class Meta:
        verbose_name = "Станция ТО"
        verbose_name_plural = "Станции ТО"

    def __str__(self):
        return self.name

    def get_working_hours(self, date):
        """
        Возвращает (work_start, work_end) на конкретную дату.
        Сначала исключения (конкретные даты), потом недельный график.
        """
        schedule = self.schedules.filter(date=date).first()
        if schedule:
            return schedule.work_start, schedule.work_end

        weekday = date.weekday()
        weekly = self.weekly_schedules.filter(weekday=weekday).first()
        if weekly:
            return weekly.work_start, weekly.work_end

        return None, None

    def get_available_slots(self, date, vehicle_type=None):
        """
        Возвращает список свободных слотов на дату.
        FIX: принимает vehicle_type чтобы корректно фильтровать
        слоты для грузовых ТС (им нужен двойной слот).
        FIX: явное исключение в StationSchedule имеет приоритет над
        праздниками — если администратор явно задал расписание на
        праздничный день, станция работает по нему.
        """
        import holidays as holidays_lib

        # Сначала проверяем явное исключение на конкретную дату
        explicit_schedule = self.schedules.filter(date=date).first()

        if explicit_schedule:
            # Явное расписание главнее праздников
            work_start = explicit_schedule.work_start
            work_end = explicit_schedule.work_end
        else:
            # Явного расписания нет — проверяем праздник
            ru_holidays = holidays_lib.Russia(years=date.year)
            if date in ru_holidays:
                return []

            # Не праздник — берём недельное расписание
            weekday = date.weekday()
            weekly = self.weekly_schedules.filter(weekday=weekday).first()
            if not weekly:
                return []
            work_start = weekly.work_start
            work_end = weekly.work_end

        if not work_start or not work_end or work_start >= work_end:
            return []

        slots = []
        slot_mins = self.slot_duration
        required_mins = slot_mins * 2 if vehicle_type == "TRUCK" else slot_mins

        from django.utils import timezone
        start_dt = make_aware(datetime.combine(date, work_start))
        end_dt = make_aware(datetime.combine(date, work_end))
        now = timezone.now()

        while start_dt + timedelta(minutes=required_mins) <= end_dt:
            slot_end = start_dt + timedelta(minutes=required_mins)

            # FIX: отменённые записи не должны блокировать слот
            conflict = Appointment.objects.filter(
                station=self,
                start__lt=slot_end,
                end__gt=start_dt,
            ).exclude(status="CANCELLED").exists()

            blocked = SlotBlock.objects.filter(
                station=self,
                start__lt=slot_end,
                end__gt=start_dt
            ).exists()

            if not conflict and not blocked and start_dt > now:
                slots.append({
                    "start": start_dt.isoformat(),
                    "end": slot_end.isoformat(),
                })

            start_dt += timedelta(minutes=slot_mins)

        return slots


# =========================
# НЕДЕЛЬНЫЙ ГРАФИК
# =========================

class StationWeeklySchedule(models.Model):
    WEEKDAYS = [
        (0, "Понедельник"),
        (1, "Вторник"),
        (2, "Среда"),
        (3, "Четверг"),
        (4, "Пятница"),
        (5, "Суббота"),
        (6, "Воскресенье"),
    ]

    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="weekly_schedules",
        verbose_name="Станция"
    )
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


# =========================
# ИСКЛЮЧЕНИЯ (КОНКРЕТНЫЕ ДАТЫ)
# =========================

class StationSchedule(models.Model):
    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="schedules",
        verbose_name="Станция"
    )
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


# =========================
# ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ
# =========================

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    first_name = models.CharField("Имя", max_length=100, blank=True)
    last_name = models.CharField("Фамилия", max_length=100, blank=True)
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


# =========================
# СПРАВОЧНИК МАРОК
# =========================

class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Марка"
        verbose_name_plural = "Марки"
        ordering = ["name"]

    def __str__(self):
        return self.name


# =========================
# СПРАВОЧНИК МОДЕЛЕЙ
# =========================

class CarModel(models.Model):
    VEHICLE_TYPES = [
        ("CAR", "Легковой"),
        ("TRUCK", "Грузовой"),
    ]

    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="models")
    name = models.CharField(max_length=100)
    vehicle_type = models.CharField(
        "Тип ТС",
        max_length=10,
        choices=VEHICLE_TYPES,
        default="CAR"
    )

    class Meta:
        unique_together = ("brand", "name")
        verbose_name = "Модель"
        verbose_name_plural = "Модели"

    def __str__(self):
        return f"{self.brand} {self.name}"


# =========================
# АВТОМОБИЛЬ ПОЛЬЗОВАТЕЛЯ
# =========================

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


# =========================
# ЗАПИСЬ НА ТО
# =========================

class Appointment(models.Model):
    # FIX: STATUS_CHOICES объявлен ДО поля status (было наоборот)
    STATUS_CHOICES = [
        ("BOOKED", "Запланировано"),
        ("CANCELLED", "Отменено"),
        ("DONE", "Выполнено"),
        ("NO_SHOW", "Не приехал"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name="Пользователь"
    )
    car = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name="Автомобиль"
    )
    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        verbose_name="Станция"
    )

    start = models.DateTimeField("Начало")
    end = models.DateTimeField("Конец")

    # Snapshot имени и телефона клиента на момент записи
    # (намеренная денормализация — для истории)
    name = models.CharField("Имя клиента", max_length=100)
    phone = models.CharField("Телефон", max_length=20, blank=True, null=True)

    # Snapshot VIN на момент записи
    # Если VIN машины изменится, старые записи сохраняют актуальный на тот момент VIN
    vin = models.CharField("VIN", max_length=32, blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="BOOKED",
        verbose_name="Статус"
    )

    # Комментарий оператора — что выявили, что сделали
    notes = models.TextField("Комментарий оператора", blank=True, default="")

    class Meta:
        ordering = ["start"]
        verbose_name = "Запись на ТО"
        verbose_name_plural = "Записи на ТО"
        # FIX: индексы для ускорения запросов на конфликты слотов
        indexes = [
            models.Index(fields=["station", "start", "end"]),
            models.Index(fields=["user", "start"]),
        ]

    def __str__(self):
        return f"{self.station} — {self.start:%d.%m %H:%M}"

    def get_required_duration(self):
        base = timedelta(minutes=self.station.slot_duration)
        if self.car.model.vehicle_type == "TRUCK":
            return base * 2
        return base

    def clean(self):
        # Если запись уже существует и меняется только статус — пропускаем валидацию
        if self.pk:
            try:
                old = Appointment.objects.get(pk=self.pk)
                if old.start == self.start and old.end == self.end and old.station == self.station:
                    return  # только статус изменился — валидация не нужна
            except Appointment.DoesNotExist:
                pass

        if self.start >= self.end:
            raise ValidationError("Время окончания должно быть позже начала")

        date = self.start.date()
        work_start, work_end = self.station.get_working_hours(date)

        if not work_start or not work_end:
            raise ValidationError("Станция не работает в этот день")

        if not (work_start <= self.start.time() < work_end):
            raise ValidationError("Запись вне графика работы станции")

        # FIX: проверяем что конец записи не выходит за рабочее время.
        # Пересчитываем expected_end самостоятельно — это важно при вызове
        # из admin-формы, где clean() срабатывает до save() и self.end
        # может содержать старое значение из БД.
        expected_end = self.start + self.get_required_duration()
        if expected_end.time() > work_end:
            raise ValidationError(
                f"Запись заканчивается в {expected_end.strftime('%H:%M')}, "
                f"станция работает до {work_end.strftime('%H:%M')}"
            )

        # FIX: проверка конфликта только среди не-отменённых записей
        conflict = Appointment.objects.filter(
            station=self.station,
            start__lt=self.end,
            end__gt=self.start,
        ).exclude(pk=self.pk).exclude(status="CANCELLED")

        if conflict.exists():
            raise ValidationError("Выбранное время уже занято")

    def save(self, *args, **kwargs):
        # При отмене не пересчитываем и не валидируем
        if self.status in ("CANCELLED", "DONE", "NO_SHOW"):
            super().save(*args, **kwargs)
            return
        # Авто-расчёт длительности на основе типа ТС
        duration = self.get_required_duration()
        self.end = self.start + duration
        self.full_clean()
        super().save(*args, **kwargs)


# =========================
# ФОТО ПРИ ЗАПИСИ
# =========================

class AppointmentPhoto(models.Model):
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="photos"
    )
    image = models.ImageField(upload_to="appointments/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Фото записи"
        verbose_name_plural = "Фото записей"

    # FIX: добавлен __str__ для отображения в admin
    def __str__(self):
        return f"Фото #{self.pk} к записи #{self.appointment_id}"


# =========================
# ПЕРСОНАЛ СТАНЦИИ
# =========================

class StationStaff(models.Model):
    ROLE_OWNER    = "OWNER"
    ROLE_OPERATOR = "OPERATOR"
    ROLE_CHOICES  = [
        (ROLE_OWNER,    "Владелец"),
        (ROLE_OPERATOR, "Оператор"),
    ]

    station    = models.ForeignKey(Station, on_delete=models.CASCADE,
                                   related_name="staff", verbose_name="Станция")
    user       = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name="station_roles", verbose_name="Пользователь")
    role       = models.CharField("Роль", max_length=10, choices=ROLE_CHOICES)
    is_active  = models.BooleanField("Активен", default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                   null=True, blank=True,
                                   related_name="created_staff",
                                   verbose_name="Кто создал")
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        unique_together = ("station", "user")
        verbose_name = "Сотрудник станции"
        verbose_name_plural = "Сотрудники станций"
        indexes = [
            models.Index(fields=["user", "role", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user} — {self.get_role_display()} @ {self.station}"

    def is_owner(self):
        return self.role == self.ROLE_OWNER

    def is_operator(self):
        return self.role == self.ROLE_OPERATOR


# =========================
# БЛОКИРОВКА СЛОТА
# =========================

class SlotBlock(models.Model):
    station    = models.ForeignKey(Station, on_delete=models.CASCADE,
                                   related_name="slot_blocks", verbose_name="Станция")
    start      = models.DateTimeField("Начало блокировки")
    end        = models.DateTimeField("Конец блокировки")
    reason     = models.CharField("Причина", max_length=255, blank=True, default="")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                   null=True, related_name="slot_blocks",
                                   verbose_name="Кто заблокировал")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start"]
        verbose_name = "Блокировка слота"
        verbose_name_plural = "Блокировки слотов"
        indexes = [
            models.Index(fields=["station", "start", "end"]),
        ]

    def __str__(self):
        return f"{self.station} заблокирован {self.start:%d.%m %H:%M}–{self.end:%H:%M}"

    def clean(self):
        if self.start >= self.end:
            raise ValidationError("Конец блокировки должен быть позже начала")


# =========================
# ИСТОРИЯ СТАТУСОВ ЗАПИСИ
# =========================

class AppointmentLog(models.Model):
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name="Запись"
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Кто изменил"
    )
    old_status = models.CharField("Старый статус", max_length=20, blank=True)
    new_status = models.CharField("Новый статус", max_length=20)
    comment    = models.TextField("Комментарий", blank=True, default="")
    created_at = models.DateTimeField("Время", auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Запись в журнале"
        verbose_name_plural = "Журнал записей"

    def __str__(self):
        return f"#{self.appointment_id} {self.old_status}→{self.new_status} {self.created_at:%d.%m %H:%M}"
