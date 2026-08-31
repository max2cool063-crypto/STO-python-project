from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def copy_names_to_user(apps, schema_editor):
    UserProfile = apps.get_model("booking", "UserProfile")
    for profile in UserProfile.objects.select_related("user").all():
        user = profile.user
        changed = False
        if profile.first_name and not user.first_name:
            user.first_name = profile.first_name
            changed = True
        if profile.last_name and not user.last_name:
            user.last_name = profile.last_name
            changed = True
        if changed:
            user.save(update_fields=["first_name", "last_name"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0019_station_rsa_id"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(copy_names_to_user, noop_reverse),
        migrations.RemoveField(model_name="userprofile", name="first_name"),
        migrations.RemoveField(model_name="userprofile", name="last_name"),
        migrations.AlterModelOptions(
            name="appointmentlog",
            options={
                "ordering": ["created_at"],
                "verbose_name": "Запись в журнале",
                "verbose_name_plural": "Журнал записей",
            },
        ),
        migrations.AlterField(
            model_name="appointmentlog",
            name="appointment",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="logs",
                to="booking.appointment",
                verbose_name="Запись",
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
                verbose_name="Кто изменил",
            ),
        ),
        migrations.AlterField(
            model_name="appointmentlog",
            name="comment",
            field=models.TextField(blank=True, default="", verbose_name="Комментарий"),
        ),
        migrations.AlterField(
            model_name="appointmentlog",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, verbose_name="Время"),
        ),
        migrations.AlterField(
            model_name="appointmentlog",
            name="new_status",
            field=models.CharField(max_length=20, verbose_name="Новый статус"),
        ),
        migrations.AlterField(
            model_name="appointmentlog",
            name="old_status",
            field=models.CharField(blank=True, max_length=20, verbose_name="Старый статус"),
        ),
    ]
