from django.db.models.signals import post_save
from django.dispatch import receiver

from booking.models import Station


@receiver(post_save, sender=Station)
def deactivate_rsa_imported_station(sender, instance, created, **kwargs):
    """Stations created from the RSA registry must be reviewed before booking."""
    if created and instance.rsa_id and instance.is_active:
        sender.objects.filter(pk=instance.pk).update(is_active=False)
