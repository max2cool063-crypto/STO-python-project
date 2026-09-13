from django.db import migrations, models


def copy_vehicle_types(apps, schema_editor):
    Car = apps.get_model("booking", "Car")
    CarModel = apps.get_model("booking", "CarModel")
    alias = schema_editor.connection.alias
    trucks = CarModel.objects.using(alias).filter(vehicle_type="TRUCK").values("pk")
    Car.objects.using(alias).filter(model_id__in=trucks).update(vehicle_type="TRUCK")


class Migration(migrations.Migration):
    dependencies = [("booking", "0028_email_schedule_revision")]
    operations = [
        migrations.AddField(
            model_name="car", name="vehicle_type",
            field=models.CharField("Тип ТС", max_length=10,
                                   choices=[("CAR", "Легковой"), ("TRUCK", "Грузовой")], default="CAR"),
        ),
        migrations.RunPython(copy_vehicle_types, migrations.RunPython.noop),
        migrations.RemoveField(model_name="carmodel", name="vehicle_type"),
    ]
