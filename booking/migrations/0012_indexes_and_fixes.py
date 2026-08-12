from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0011_appointment_status"),
    ]

    operations = [
        # FIX: добавлены индексы для ускорения запросов на конфликты слотов
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(fields=["station", "start", "end"], name="booking_apt_station_start_end_idx"),
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(fields=["user", "start"], name="booking_apt_user_start_idx"),
        ),
        # FIX: добавлена сортировка для Brand
        migrations.AlterModelOptions(
            name="brand",
            options={"ordering": ["name"], "verbose_name": "\u041c\u0430\u0440\u043a\u0430", "verbose_name_plural": "\u041c\u0430\u0440\u043a\u0438"},
        ),
    ]
