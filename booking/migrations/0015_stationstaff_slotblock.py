from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0014_station_is_active"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StationStaff",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("OWNER", "Владелец"), ("OPERATOR", "Оператор")], max_length=10, verbose_name="Роль")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")),
                ("station", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="staff", to="booking.station", verbose_name="Станция")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="station_roles", to=settings.AUTH_USER_MODEL, verbose_name="Пользователь")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_staff", to=settings.AUTH_USER_MODEL, verbose_name="Кто создал")),
            ],
            options={
                "verbose_name": "Сотрудник станции",
                "verbose_name_plural": "Сотрудники станций",
            },
        ),
        migrations.AddConstraint(
            model_name="stationstaff",
            constraint=models.UniqueConstraint(fields=["station", "user"], name="unique_station_user"),
        ),
        migrations.AddIndex(
            model_name="stationstaff",
            index=models.Index(fields=["user", "role", "is_active"], name="booking_sta_user_id_role_is_active_idx"),
        ),
        migrations.CreateModel(
            name="SlotBlock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("start", models.DateTimeField(verbose_name="Начало блокировки")),
                ("end", models.DateTimeField(verbose_name="Конец блокировки")),
                ("reason", models.CharField(blank=True, default="", max_length=255, verbose_name="Причина")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("station", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="slot_blocks", to="booking.station", verbose_name="Станция")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="slot_blocks", to=settings.AUTH_USER_MODEL, verbose_name="Кто заблокировал")),
            ],
            options={
                "verbose_name": "Блокировка слота",
                "verbose_name_plural": "Блокировки слотов",
                "ordering": ["start"],
            },
        ),
        migrations.AddIndex(
            model_name="slotblock",
            index=models.Index(fields=["station", "start", "end"], name="booking_slotblock_station_start_end_idx"),
        ),
    ]
