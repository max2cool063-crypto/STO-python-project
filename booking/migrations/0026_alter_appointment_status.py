from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0025_alter_notification_notification_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="appointment",
            name="status",
            field=models.CharField(
                choices=[
                    ("BOOKED", "Запланировано"),
                    ("AWAITING_RESULT", "Требует результата"),
                    ("CANCELLED", "Отменено"),
                    ("DONE", "Выполнено"),
                    ("NO_SHOW", "Не приехал"),
                ],
                default="BOOKED",
                max_length=20,
                verbose_name="Статус",
            ),
        ),
    ]
