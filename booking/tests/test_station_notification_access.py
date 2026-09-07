from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from booking.models import Notification, Station, StationStaff


class StationNotificationAccessTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(
            username="notification-operator",
            password="test-password",
        )
        self.client_user = User.objects.create_user(
            username="notification-client",
            password="test-password",
        )
        self.station = Station.objects.create(name="Station A")
        self.other_station = Station.objects.create(name="Station B")
        self.staff_record = StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        self.own_notification = Notification.objects.create(
            recipient=self.operator,
            station=self.station,
            notification_type=Notification.TYPE_NEW_APPOINTMENT,
            title="Own station",
            message="Own station message",
        )
        self.foreign_notification = Notification.objects.create(
            recipient=self.operator,
            station=self.other_station,
            notification_type=Notification.TYPE_NEW_APPOINTMENT,
            title="Foreign station",
            message="Foreign station message",
        )

    def login_operator(self):
        self.client.login(username="notification-operator", password="test-password")

    def test_notifications_endpoint_returns_only_accessible_station(self):
        self.login_operator()

        response = self.client.get(reverse("station_notifications"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["unread_count"], 1)
        self.assertEqual([item["id"] for item in payload["notifications"]], [self.own_notification.id])

    def test_notification_history_excludes_foreign_station(self):
        self.login_operator()

        response = self.client.get(reverse("station_notifications_history"))

        self.assertEqual(response.status_code, 200)
        notifications = list(response.context["notifications"])
        self.assertEqual([item.id for item in notifications], [self.own_notification.id])

    def test_notification_read_cannot_mark_foreign_station_notification(self):
        self.login_operator()

        response = self.client.post(
            reverse("station_notification_read", kwargs={"pk": self.foreign_notification.id})
        )

        self.assertEqual(response.status_code, 404)
        self.foreign_notification.refresh_from_db()
        self.assertFalse(self.foreign_notification.is_read)

    def test_read_all_only_marks_accessible_station_notifications(self):
        self.login_operator()

        response = self.client.post(reverse("station_notifications_read_all"))

        self.assertEqual(response.status_code, 200)
        self.own_notification.refresh_from_db()
        self.foreign_notification.refresh_from_db()
        self.assertTrue(self.own_notification.is_read)
        self.assertFalse(self.foreign_notification.is_read)

    def test_deactivated_staff_cannot_read_old_station_notifications(self):
        self.staff_record.is_active = False
        self.staff_record.save(update_fields=["is_active"])
        self.login_operator()

        response = self.client.get(reverse("station_notifications_history"))

        self.assertEqual(response.status_code, 403)

    def test_regular_client_cannot_use_station_notifications(self):
        self.client.login(username="notification-client", password="test-password")

        response = self.client.get(reverse("station_notifications"))

        self.assertEqual(response.status_code, 403)
