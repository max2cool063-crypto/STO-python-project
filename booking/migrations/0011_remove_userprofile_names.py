from django.db import migrations


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
    # Names remain stored in auth.User, so reversing the schema migration
    # does not need to duplicate them back into UserProfile.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0010_car_is_active_alter_carmodel_vehicle_type"),
    ]

    operations = [
        migrations.RunPython(copy_names_to_user, noop_reverse),
        migrations.RemoveField(model_name="userprofile", name="first_name"),
        migrations.RemoveField(model_name="userprofile", name="last_name"),
    ]
