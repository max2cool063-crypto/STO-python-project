from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0024_appointment_reminder_sent_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="notification_type",
            field=models.CharField(
                choices=[
                    ("NEW_APPOINTMENT", "Новая запись"),
                    ("APPOINTMENT_CANCELLED", "Запись отменена"),
                ],
                max_length=50,
                verbose_name="Тип",
            ),
        ),
    ]
