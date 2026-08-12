from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0015_stationstaff_slotblock"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="notes",
            field=models.TextField(blank=True, default="", verbose_name="Комментарий оператора"),
        ),
        migrations.CreateModel(
            name="AppointmentLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("old_status", models.CharField(blank=True, max_length=20, verbose_name="Старый статус")),
                ("new_status", models.CharField(max_length=20, verbose_name="Новый статус")),
                ("comment", models.TextField(blank=True, default="", verbose_name="Комментарий")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Время")),
                ("appointment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="logs", to="booking.appointment", verbose_name="Запись")),
                ("changed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name="Кто изменил")),
            ],
            options={
                "verbose_name": "Запись в журнале",
                "verbose_name_plural": "Журнал записей",
                "ordering": ["created_at"],
            },
        ),
    ]
