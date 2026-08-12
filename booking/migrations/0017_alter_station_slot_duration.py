from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0016_appointment_notes_appointmentlog"),
    ]

    operations = [
        migrations.AlterField(
            model_name="station",
            name="slot_duration",
            field=models.PositiveIntegerField(
                default=30,
                verbose_name="Длительность базового слота (мин)",
            ),
        ),
    ]
