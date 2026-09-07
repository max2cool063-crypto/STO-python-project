from django.contrib.admin.apps import AdminConfig


class SuperuserOnlyAdminConfig(AdminConfig):
    default_site = "auto_booking.admin_site.SuperuserOnlyAdminSite"
