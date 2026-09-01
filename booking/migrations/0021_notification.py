from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("booking", "0020_remove_userprofile_names"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("notification_type", models.CharField(choices=[("NEW_APPOINTMENT", "Новая запись")], max_length=50, verbose_name="Тип")),
                ("title", models.CharField(max_length=255, verbose_name="Заголовок")),
                ("message", models.TextField(verbose_name="Сообщение")),
                ("is_read", models.BooleanField(db_index=True, default=False, verbose_name="Прочитано")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Создано")),
                ("appointment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="booking.appointment", verbose_name="Запись")),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL, verbose_name="Получатель")),
                ("station", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="booking.station", verbose_name="Станция")),
            ],
            options={
                "verbose_name": "Уведомление",
                "verbose_name_plural": "Уведомления",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["recipient", "is_read", "created_at"], name="booking_not_recipie_a78cff_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["station", "created_at"], name="booking_not_station_99eb13_idx"),
        ),
    ]
