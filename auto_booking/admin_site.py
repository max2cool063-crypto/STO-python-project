from django.contrib.admin import AdminSite


class SuperuserOnlyAdminSite(AdminSite):
    """Django Admin is reserved for trusted system superusers only."""

    def has_permission(self, request):
        user = request.user
        return bool(user.is_active and user.is_superuser)
