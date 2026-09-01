from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0021_notification"),
    ]

    operations = [
        migrations.AddField(
            model_name="stationstaff",
            name="receive_notifications",
            field=models.BooleanField(
                default=True,
                verbose_name="Получать уведомления о новых записях",
            ),
        ),
    ]
