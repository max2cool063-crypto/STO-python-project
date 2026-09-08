from django.contrib import admin
from django.contrib.auth.models import User
from django.db import transaction

from booking.admin import (
    AppointmentAdmin as BaseAppointmentAdmin,
    BrandAdmin as BaseBrandAdmin,
    CarAdmin as BaseCarAdmin,
    CarModelAdmin as BaseCarModelAdmin,
    StationStaffAdmin as BaseStationStaffAdmin,
    UserAdmin as BaseUserAdmin,
)
from booking.admin_timezone import StationTimezoneAdmin as BaseStationAdmin
from booking.forms import normalize_ru_phone
from booking.models import (
    Appointment,
    AppointmentLog,
    Brand,
    Car,
    CarModel,
    Station,
    StationStaff,
)


class NoHardDeleteAdminMixin:
    """Keep production history intact; use status/active flags instead."""

    def has_delete_permission(self, request, obj=None):
        return False


class ReferencedObjectDeleteAdminMixin:
    """Allow deliberate cleanup only for objects that have no dependants."""

    def has_delete_permission(self, request, obj=None):
        # Never expose Django's bulk ``delete_selected`` action. Object-level
        # deletion is evaluated separately on the change page.
        if obj is None:
            return False
        return super().has_delete_permission(request, obj) and self.can_hard_delete(obj)

    def can_hard_delete(self, obj):
        raise NotImplementedError


class SafeStationAdmin(NoHardDeleteAdminMixin, BaseStationAdmin):
    pass


class SafeAppointmentAdmin(NoHardDeleteAdminMixin, BaseAppointmentAdmin):
    # Status changes are operational workflow and should normally happen in the
    # station cabinet, where logging/notifications are applied. Keep the status
    # visible here, but remove changelist mass/quick editing.
    list_editable = ()

    def save_model(self, request, obj, form, change):
        """Keep emergency Admin status corrections inside the audit trail."""
        old_status = None
        if change and obj.pk:
            old_status = (
                Appointment.objects.filter(pk=obj.pk)
                .values_list("status", flat=True)
                .first()
            )

        with transaction.atomic():
            super().save_model(request, obj, form, change)
            if old_status is not None and old_status != obj.status:
                AppointmentLog.objects.create(
                    appointment=obj,
                    changed_by=request.user,
                    old_status=old_status,
                    new_status=obj.status,
                    comment="Изменено через Django Admin",
                )


class SafeCarAdmin(NoHardDeleteAdminMixin, BaseCarAdmin):
    pass


class NormalizedAdminPhoneMixin:
    """Apply the same Russian phone normalization used by client/station forms."""

    def clean_phone(self):
        return normalize_ru_phone(self.cleaned_data.get("phone", ""))


class SafeUserAdminChangeForm(NormalizedAdminPhoneMixin, BaseUserAdmin.form):
    pass


class SafeUserAdminCreationForm(NormalizedAdminPhoneMixin, BaseUserAdmin.add_form):
    pass


class SafeUserAdmin(NoHardDeleteAdminMixin, BaseUserAdmin):
    form = SafeUserAdminChangeForm
    add_form = SafeUserAdminCreationForm


class SafeStationStaffAdmin(NoHardDeleteAdminMixin, BaseStationStaffAdmin):
    # A staff identity belongs to the station history permanently. Operators
    # can only be activated/deactivated on their original station.
    list_editable = ("is_active",)

    def get_readonly_fields(self, request, obj=None):
        readonly = tuple(super().get_readonly_fields(request, obj))
        if obj is not None:
            readonly += ("station", "user", "role")
        return readonly


class SafeBrandAdmin(ReferencedObjectDeleteAdminMixin, BaseBrandAdmin):
    def can_hard_delete(self, obj):
        # Deleting a brand cascades into its models, so require explicit model
        # cleanup first rather than allowing a broad cascade from this screen.
        return not obj.models.exists()


class SafeCarModelAdmin(ReferencedObjectDeleteAdminMixin, BaseCarModelAdmin):
    def can_hard_delete(self, obj):
        # A model used by any car is part of vehicle/appointment history.
        return not Car.objects.filter(model=obj).exists()


# booking.admin registers these models during Django admin autodiscovery, and
# booking.admin_timezone replaces Station once to add the timezone field. Apply
# the safety layer last so existing admin UI/custom behavior is preserved.
for model, admin_class in (
    (Station, SafeStationAdmin),
    (Appointment, SafeAppointmentAdmin),
    (Car, SafeCarAdmin),
    (User, SafeUserAdmin),
    (StationStaff, SafeStationStaffAdmin),
    (Brand, SafeBrandAdmin),
    (CarModel, SafeCarModelAdmin),
):
    admin.site.unregister(model)
    admin.site.register(model, admin_class)
