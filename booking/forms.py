import re

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


# Идентификаторы ТС и телефон: единые правила для кабинета клиента
# и ручной записи оператором.
RUSSIAN_PLATE_RE = re.compile(r"^[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}$")
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


def normalize_ru_phone(value):
    """Normalize a Russian phone to +7XXXXXXXXXX."""
    raw = (value or "").strip()
    if not raw:
        return ""

    digits = re.sub(r"\D", "", raw)
    if digits.startswith("8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    elif digits.startswith("7"):
        pass
    else:
        raise ValidationError("Телефон должен быть российским номером в формате +7 XXX XXX-XX-XX")

    if len(digits) != 11 or not digits.startswith("7"):
        raise ValidationError("Телефон должен содержать 10 цифр после кода +7")
    if digits[1] not in "3456789":
        raise ValidationError("Укажите корректный российский номер телефона")
    return "+" + digits


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


class ProfileForm(forms.Form):
    """Редактирование имени/фамилии из User и телефона из UserProfile."""
    first_name = forms.CharField(label="Имя", max_length=150, required=False)
    last_name = forms.CharField(label="Фамилия", max_length=150, required=False)
    phone = forms.CharField(
        label="Телефон",
        max_length=16,
        required=False,
        widget=forms.TextInput(attrs={
            "inputmode": "tel",
            "autocomplete": "tel",
            "maxlength": "16",
            "placeholder": "+7 900 000-00-00",
        }),
    )

    def __init__(self, *args, user=None, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user or (profile.user if profile else None)
        self.profile = profile
        if not self.is_bound and self.user is not None:
            self.initial.update({
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "phone": self.profile.phone if self.profile else "",
            })

    def clean_phone(self):
        return normalize_ru_phone(self.cleaned_data.get("phone", ""))

    def save(self):
        if self.user is None:
            raise ValueError("ProfileForm requires a user")
        self.user.first_name = self.cleaned_data["first_name"].strip()
        self.user.last_name = self.cleaned_data["last_name"].strip()
        self.user.save(update_fields=["first_name", "last_name"])
        profile = self.profile or UserProfile.objects.get_or_create(user=self.user)[0]
        profile.phone = self.cleaned_data["phone"]
        profile.save(update_fields=["phone"])
        return profile


class CarForm(forms.ModelForm):
    """Форма редактирования автомобиля."""
    class Meta:
        model = Car
        fields = ["plate_number", "vin"]
        widgets = {
            "plate_number": forms.TextInput(attrs={
                "maxlength": "9",
                "pattern": r"[АВЕКМНОРСТУХ]{1}[0-9]{3}[АВЕКМНОРСТУХ]{2}[0-9]{2,3}",
                "placeholder": "А123ВС77",
                "style": "text-transform:uppercase",
                "oninput": "this.value=this.value.toUpperCase()",
            }),
            "vin": forms.TextInput(attrs={
                "maxlength": "17",
                "pattern": r"[A-HJ-NPR-Z0-9]{17}",
                "placeholder": "17 символов",
                "style": "text-transform:uppercase",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vin"].required = False

    def clean_plate_number(self):
        plate = (self.cleaned_data.get("plate_number") or "").strip().upper()
        if not RUSSIAN_PLATE_RE.fullmatch(plate):
            raise forms.ValidationError(
                "Госномер должен соответствовать российскому формату: А123ВС77 или А123ВС777"
            )
        return plate

    def clean_vin(self):
        vin = (self.cleaned_data.get("vin") or "").strip().upper()
        if vin and not VIN_RE.fullmatch(vin):
            raise forms.ValidationError(
                "VIN должен содержать ровно 17 символов: латинские буквы и цифры, без I, O и Q"
            )
        return vin or None


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
