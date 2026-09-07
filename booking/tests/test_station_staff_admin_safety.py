from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

import booking.admin_safety  # noqa: F401
from booking.models import Station, StationStaff


class StationStaffAdminSafetyTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="staff-admin-root",
            password="Admin-password-123!",
        )
        self.operator = User.objects.create_user(username="admin-safety-operator")
        self.station = Station.objects.create(name="Admin safety station")
        self.assignment = StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
        )
        self.factory = RequestFactory()

    def request(self):
        request = self.factory.get("/admin/")
        request.user = self.superuser
        return request

    def test_station_staff_cannot_be_hard_deleted(self):
        model_admin = admin.site._registry[StationStaff]
        request = self.request()

        self.assertFalse(model_admin.has_delete_permission(request, self.assignment))
        self.assertNotIn("delete_selected", model_admin.get_actions(request))

    def test_existing_assignment_identity_is_read_only(self):
        model_admin = admin.site._registry[StationStaff]
        readonly = model_admin.get_readonly_fields(self.request(), self.assignment)

        self.assertIn("station", readonly)
        self.assertIn("user", readonly)
        self.assertIn("role", readonly)
        self.assertEqual(model_admin.list_editable, ("is_active",))
