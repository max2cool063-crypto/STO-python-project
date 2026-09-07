from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0023_station_timezone"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="reminder_sent_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Напоминание отправлено",
            ),
        ),
    ]
