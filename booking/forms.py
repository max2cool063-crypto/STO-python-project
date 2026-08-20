from django import forms
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

from .models import Appointment, UserProfile, Car, StationWeeklySchedule, StationSchedule

TIME_CHOICES = [("", "—")] + [
    (f"{h:02d}:{m:02d}:00", f"{h:02d}:{m:02d}")
    for h in range(0, 24) for m in (0, 30)
]


class WeeklyScheduleInlineForm(forms.ModelForm):
    class Meta:
        model = StationWeeklySchedule
        fields = "__all__"
        widgets = {
            "weekday": forms.Select(attrs={"style": "width:150px"}),
            "work_start": forms.Select(choices=TIME_CHOICES, attrs={"style": "width:120px"}),
            "work_end": forms.Select(choices=TIME_CHOICES, attrs={"style": "width:120px"}),
        }


class ScheduleInlineForm(forms.ModelForm):
    class Meta:
        model = StationSchedule
        fields = "__all__"
        widgets = {
            "work_start": forms.Select(choices=TIME_CHOICES),
            "work_end": forms.Select(choices=TIME_CHOICES),
        }


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_PHOTO_SIZE_MB = 5
MAX_PHOTOS = 5


class AppointmentForm(forms.ModelForm):
    """Форма бронирования — используется в admin и потенциально в view."""
    class Meta:
        model = Appointment
        fields = ["station", "start", "end", "name", "phone", "vin"]

    def clean(self):
        cleaned = super().clean()
        station = cleaned.get("station")
        start = cleaned.get("start")
        end = cleaned.get("end")

        if station and start and end:
            exists = Appointment.objects.filter(
                station=station,
                start__lt=end,
                end__gt=start,
            ).exclude(status="CANCELLED").exists()

            if exists:
                raise forms.ValidationError("Выбранное время уже занято")

        return cleaned


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["first_name", "last_name", "phone"]
        widgets = {
            "first_name": forms.TextInput(attrs={"maxlength": 100}),
            "last_name": forms.TextInput(attrs={"maxlength": 100}),
            "phone": forms.TextInput(attrs={"maxlength": 30}),
        }


class CarForm(forms.ModelForm):
    """Форма редактирования автомобиля."""
    class Meta:
        model = Car
        fields = ["plate_number", "vin"]
        widgets = {
            "plate_number": forms.TextInput(attrs={
                "style": "text-transform:uppercase",
                "oninput": "this.value=this.value.toUpperCase()"
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vin"].required = False


class PhotosUploadForm:
    """Валидация количества, размера, MIME-типа и фактического формата файлов."""

    @staticmethod
    def validate_photos(files):
        errors = []
        if len(files) > MAX_PHOTOS:
            errors.append(f"Максимум {MAX_PHOTOS} фото")
            return errors

        for uploaded in files:
            if uploaded.content_type not in ALLOWED_IMAGE_TYPES:
                errors.append(f"Файл «{uploaded.name}»: допустимые форматы JPEG, PNG, WebP, GIF")
                continue

            if uploaded.size > MAX_PHOTO_SIZE_MB * 1024 * 1024:
                errors.append(f"Файл «{uploaded.name}»: размер превышает {MAX_PHOTO_SIZE_MB} МБ")
                continue

            try:
                uploaded.seek(0)
                with Image.open(uploaded) as image:
                    image.verify()
            except (UnidentifiedImageError, OSError, ValueError):
                errors.append(f"Файл «{uploaded.name}»: файл не является корректным изображением")
            finally:
                uploaded.seek(0)

        return errors
