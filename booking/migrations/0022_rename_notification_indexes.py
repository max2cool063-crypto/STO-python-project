from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0021_notification"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="notification",
            old_name="booking_not_recipie_0f2b8d_idx",
            new_name="booking_not_recipie_a78cff_idx",
        ),
        migrations.RenameIndex(
            model_name="notification",
            old_name="booking_not_station_4e5a3f_idx",
            new_name="booking_not_station_99eb13_idx",
        ),
    ]
