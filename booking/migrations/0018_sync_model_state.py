from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0017_alter_station_slot_duration"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="appointmentlog",
            options={
                "ordering": ["-created_at"],
                "verbose_name": "Лог записи",
                "verbose_name_plural": "Логи записей",
            },
        ),
        migrations.RemoveConstraint(
            model_name="stationstaff",
            name="unique_station_user",
        ),
        migrations.RenameIndex(
            model_name="slotblock",
            old_name="booking_slotblock_station_start_end_idx",
            new_name="booking_slo_station_cda28c_idx",
        ),
        migrations.RenameIndex(
            model_name="stationstaff",
            old_name="booking_sta_user_id_role_is_active_idx",
            new_name="booking_sta_user_id_f0c635_idx",
        ),
        migrations.AlterField(
            model_name="appointmentlog",
            name="appointment",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="logs",
                to="booking.appointment",
            ),
        ),
        migrations.AlterField(
            model_name="appointmentlog",
            name="changed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="appointmentlog",
            name="comment",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="appointmentlog",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name="appointmentlog",
            name="new_status",
            field=models.CharField(max_length=20),
        ),
        migrations.AlterField(
            model_name="appointmentlog",
            name="old_status",
            field=models.CharField(max_length=20),
        ),
        migrations.AlterField(
            model_name="slotblock",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="slotblock",
            name="station",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="slot_blocks",
                to="booking.station",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="stationstaff",
            unique_together={("station", "user")},
        ),
    ]
