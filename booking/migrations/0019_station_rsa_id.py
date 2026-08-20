from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0018_sync_model_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="station",
            name="rsa_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=20,
                null=True,
                unique=True,
                verbose_name="ID из реестра РСА (№ ОТО)",
            ),
        ),
    ]
