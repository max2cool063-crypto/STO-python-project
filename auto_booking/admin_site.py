from django.contrib.admin import AdminSite


class SuperuserOnlyAdminSite(AdminSite):
    """Django Admin is reserved for pure system-superuser identities only."""

    def has_permission(self, request):
        user = request.user
        if not (user.is_active and user.is_superuser):
            return False

        # Keep the boundary enforced even for legacy/corrupted records created
        # before the StationStaff/User validation policy existed or via raw SQL.
        from booking.models import StationStaff

        return not StationStaff.objects.filter(user_id=user.pk).exists()
