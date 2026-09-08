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
        self.assertIn("created_at", readonly)
        self.assertIn("created_by", readonly)
        self.assertEqual(model_admin.list_editable, ("is_active",))

    def test_station_staff_admin_restores_search_and_autocomplete(self):
        model_admin = admin.site._registry[StationStaff]

        self.assertEqual(
            model_admin.search_fields,
            ("user__email", "user__username", "station__name"),
        )
        self.assertEqual(model_admin.autocomplete_fields, ("user", "station"))

    def test_station_staff_admin_sets_creator_automatically(self):
        model_admin = admin.site._registry[StationStaff]
        user = User.objects.create_user(username="admin-created-operator")
        assignment = StationStaff(
            station=self.station,
            user=user,
            role=StationStaff.ROLE_OPERATOR,
        )

        model_admin.save_model(self.request(), assignment, form=None, change=False)

        assignment.refresh_from_db()
        self.assertEqual(assignment.created_by, self.superuser)

    def test_station_staff_admin_form_rejects_system_admin_identity(self):
        model_admin = admin.site._registry[StationStaff]
        form_class = model_admin.get_form(self.request())
        form = form_class(data={
            "station": self.station.pk,
            "user": self.superuser.pk,
            "role": StationStaff.ROLE_OPERATOR,
            "is_active": "on",
            "receive_notifications": "on",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("user", form.errors)
        self.assertIn("Системный администратор", form.errors["user"][0])
