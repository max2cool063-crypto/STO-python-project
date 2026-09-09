from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.template.response import TemplateResponse

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
from booking.station_staff_policy import (
    SYSTEM_ADMIN_STAFF_MESSAGE,
    validate_station_staff_assignment,
)


class NoHardDeleteAdminMixin:
    """Keep production history intact; use status/active flags instead."""

    def has_delete_permission(self, request, obj=None):
        return False


class ReferencedObjectDeleteAdminMixin:
    """Allow deliberate cleanup only for objects that have no dependants."""

    def has_delete_permission(self, request, obj=None):
        # Keep the model-level delete permission visible so Django/Jazzmin can
        # expose the object-level delete button. Actual object deletion is
        # still conditional on dependency checks below.
        if not super().has_delete_permission(request, obj):
            return False
        if obj is None:
            return True
        return self.can_hard_delete(obj)

    def get_actions(self, request):
        # Never expose Django's unrestricted bulk ``delete_selected`` action.
        # Reference models may opt into their own dependency-aware actions.
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def delete_model(self, request, obj):
        # Recheck under a row lock at the actual delete point. This closes the
        # race where a new dependent row could otherwise appear after the Admin
        # confirmation page was rendered and be removed by CASCADE.
        with transaction.atomic():
            locked_obj = self.model.objects.select_for_update().get(pk=obj.pk)
            if not self.can_hard_delete(locked_obj):
                raise PermissionDenied("Объект уже используется и не может быть удалён")
            super().delete_model(request, locked_obj)

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
    def clean_is_superuser(self):
        is_superuser = self.cleaned_data.get("is_superuser", False)
        if (
            is_superuser
            and self.instance.pk
            and StationStaff.objects.filter(user_id=self.instance.pk).exists()
        ):
            raise ValidationError(SYSTEM_ADMIN_STAFF_MESSAGE)
        return is_superuser


class SafeUserAdminCreationForm(NormalizedAdminPhoneMixin, BaseUserAdmin.add_form):
    pass


class SafeUserAdmin(NoHardDeleteAdminMixin, BaseUserAdmin):
    form = SafeUserAdminChangeForm
    add_form = SafeUserAdminCreationForm


class SafeStationStaffAdminForm(forms.ModelForm):
    """Surface station-role policy violations as normal Admin form errors."""

    class Meta:
        model = StationStaff
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        if self.errors:
            return cleaned_data

        candidate = StationStaff(pk=self.instance.pk)
        if self.instance.pk:
            candidate.station_id = self.instance.station_id
            candidate.user_id = self.instance.user_id
            candidate.role = self.instance.role
        else:
            station = cleaned_data.get("station")
            user = cleaned_data.get("user")
            candidate.station_id = station.pk if station else None
            candidate.user_id = user.pk if user else None
            candidate.role = cleaned_data.get("role")

        try:
            validate_station_staff_assignment(candidate)
        except ValidationError as exc:
            self.add_error(None, exc)

        return cleaned_data


class SafeStationStaffAdmin(NoHardDeleteAdminMixin, BaseStationStaffAdmin):
    # A staff identity belongs to the station history permanently. Operators
    # can only be activated/deactivated on their original station.
    form = SafeStationStaffAdminForm
    list_editable = ("is_active",)
    search_fields = ("user__email", "user__username", "station__name")
    autocomplete_fields = ("user", "station")
    readonly_fields = ("created_at", "created_by")

    def get_readonly_fields(self, request, obj=None):
        readonly = tuple(super().get_readonly_fields(request, obj))
        if obj is not None:
            readonly += ("station", "user", "role")
        return readonly

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class SafeBrandAdmin(ReferencedObjectDeleteAdminMixin, BaseBrandAdmin):
    def can_hard_delete(self, obj):
        # Deleting a brand cascades into its models, so require explicit model
        # cleanup first rather than allowing a broad cascade from this screen.
        return not obj.models.exists()


class SafeCarModelAdmin(ReferencedObjectDeleteAdminMixin, BaseCarModelAdmin):
    actions = ("delete_unused_models",)

    def can_hard_delete(self, obj):
        # A model used by any car is part of vehicle/appointment history.
        return not Car.objects.filter(model=obj).exists()

    @staticmethod
    def _partition_delete_candidates(models):
        model_ids = [obj.pk for obj in models]
        used_ids = set(
            Car.objects.filter(model_id__in=model_ids)
            .values_list("model_id", flat=True)
            .distinct()
        )
        deletable = [obj for obj in models if obj.pk not in used_ids]
        protected = [obj for obj in models if obj.pk in used_ids]
        return deletable, protected

    @staticmethod
    def _model_names(models):
        return ", ".join(str(obj) for obj in models)

    @admin.action(
        permissions=["delete"],
        description="Удалить выбранные неиспользуемые модели",
    )
    def delete_unused_models(self, request, queryset):
        """Bulk-delete only models that are not referenced by any vehicle."""
        selected_ids = list(queryset.values_list("pk", flat=True))
        if not selected_ids:
            return None

        if request.POST.get("apply") == "yes":
            with transaction.atomic():
                # Re-read and lock the selected models at confirmation time so
                # a model that became used in the meantime is skipped safely.
                selected_models = list(
                    CarModel.objects.select_for_update()
                    .filter(pk__in=selected_ids)
                    .select_related("brand")
                    .order_by("brand__name", "name")
                )
                deletable, protected = self._partition_delete_candidates(selected_models)

                if deletable:
                    deletable_ids = [obj.pk for obj in deletable]
                    deletable_qs = CarModel.objects.filter(pk__in=deletable_ids)
                    self.log_deletions(request, deletable_qs)
                    deleted_count = len(deletable)
                    deletable_qs.delete()
                else:
                    deleted_count = 0

            if deleted_count:
                self.message_user(
                    request,
                    f"Удалено моделей: {deleted_count}.",
                    level=messages.SUCCESS,
                )
            if protected:
                self.message_user(
                    request,
                    "Не удалены модели, которые используются автомобилями: "
                    f"{self._model_names(protected)}.",
                    level=messages.WARNING,
                )
            return None

        selected_models = list(
            CarModel.objects.filter(pk__in=selected_ids)
            .select_related("brand")
            .order_by("brand__name", "name")
        )
        deletable, protected = self._partition_delete_candidates(selected_models)

        if not deletable:
            self.message_user(
                request,
                "Ни одна из выбранных моделей не удалена: все они используются "
                f"автомобилями ({self._model_names(protected)}).",
                level=messages.WARNING,
            )
            return None

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Удаление выбранных моделей",
            "deletable_models": deletable,
            "protected_models": protected,
            "selected_models": selected_models,
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            "changelist_url": request.path,
        }
        return TemplateResponse(
            request,
            "admin/booking/carmodel/delete_unused_selected_confirmation.html",
            context,
        )


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
