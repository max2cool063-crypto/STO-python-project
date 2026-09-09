from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from booking.models import Station, StationStaff
from booking.station_access import get_user_stations


class StationAccountSeparationTests(TestCase):
    password = "Strong-test-password-123!"

    def setUp(self):
        self.station_a = Station.objects.create(name="Station A")
        self.station_b = Station.objects.create(name="Station B")
        self.station_c = Station.objects.create(name="Station C")

    def create_user(self, username):
        return User.objects.create_user(username=username, password=self.password)

    def test_owner_can_belong_to_multiple_stations(self):
        owner = self.create_user("owner-multi")
        StationStaff.objects.create(
            station=self.station_a,
            user=owner,
            role=StationStaff.ROLE_OWNER,
        )
        StationStaff.objects.create(
            station=self.station_b,
            user=owner,
            role=StationStaff.ROLE_OWNER,
        )

        self.assertEqual(
            set(get_user_stations(owner).values_list("pk", flat=True)),
            {self.station_a.pk, self.station_b.pk},
        )

    def test_operator_cannot_be_reassigned_after_deactivation(self):
        operator = self.create_user("operator-fixed")
        assignment = StationStaff.objects.create(
            station=self.station_a,
            user=operator,
            role=StationStaff.ROLE_OPERATOR,
        )
        assignment.is_active = False
        assignment.save(update_fields=["is_active"])

        with self.assertRaisesMessage(
            ValidationError,
            "Учётная запись оператора навсегда привязана только к одной станции",
        ):
            StationStaff.objects.create(
                station=self.station_b,
                user=operator,
                role=StationStaff.ROLE_OPERATOR,
            )

    def test_operator_account_cannot_be_mixed_with_owner_role(self):
        operator = self.create_user("operator-not-owner")
        StationStaff.objects.create(
            station=self.station_a,
            user=operator,
            role=StationStaff.ROLE_OPERATOR,
        )

        with self.assertRaises(ValidationError):
            StationStaff.objects.create(
                station=self.station_b,
                user=operator,
                role=StationStaff.ROLE_OWNER,
            )

    def test_owner_account_cannot_become_operator(self):
        owner = self.create_user("owner-not-operator")
        StationStaff.objects.create(
            station=self.station_a,
            user=owner,
            role=StationStaff.ROLE_OWNER,
        )

        with self.assertRaises(ValidationError):
            StationStaff.objects.create(
                station=self.station_b,
                user=owner,
                role=StationStaff.ROLE_OPERATOR,
            )

    def test_existing_staff_assignment_cannot_move_station_or_change_role(self):
        operator = self.create_user("operator-immutable")
        assignment = StationStaff.objects.create(
            station=self.station_a,
            user=operator,
            role=StationStaff.ROLE_OPERATOR,
        )

        assignment.station = self.station_b
        with self.assertRaisesMessage(ValidationError, "Нельзя перенести"):
            assignment.save()

        assignment.refresh_from_db()
        assignment.role = StationStaff.ROLE_OWNER
        with self.assertRaisesMessage(ValidationError, "Роль существующего сотрудника нельзя изменять"):
            assignment.save()

    def test_active_station_staff_cannot_open_client_cabinet(self):
        operator = self.create_user("operator-no-cabinet")
        StationStaff.objects.create(
            station=self.station_a,
            user=operator,
            role=StationStaff.ROLE_OPERATOR,
        )
        self.client.force_login(operator)

        response = self.client.get(reverse("cabinet"))

        self.assertRedirects(
            response,
            reverse("station_select"),
            fetch_redirect_response=False,
        )

    def test_active_station_staff_cannot_book_as_client(self):
        owner = self.create_user("owner-no-booking")
        StationStaff.objects.create(
            station=self.station_a,
            user=owner,
            role=StationStaff.ROLE_OWNER,
        )
        self.client.force_login(owner)

        response = self.client.get(reverse("book_station", args=[self.station_b.pk]))

        self.assertRedirects(
            response,
            reverse("station_select"),
            fetch_redirect_response=False,
        )

    def test_regular_client_keeps_client_cabinet_access(self):
        client_user = self.create_user("regular-client")
        self.client.force_login(client_user)

        response = self.client.get(reverse("cabinet"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Мои автомобили")

    def test_deactivated_operator_session_is_revoked(self):
        operator = self.create_user("operator-disabled")
        StationStaff.objects.create(
            station=self.station_a,
            user=operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=False,
        )
        self.client.force_login(operator)

        response = self.client.get(reverse("home"))

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_deactivated_operator_cannot_complete_login(self):
        operator = self.create_user("operator-disabled-login")
        StationStaff.objects.create(
            station=self.station_a,
            user=operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=False,
        )

        response = self.client.post(
            reverse("login"),
            {"username": operator.username, "password": self.password},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "Доступ учётной записи сотрудника деактивирован")

    def test_owner_stays_active_while_another_station_role_remains_active(self):
        owner = self.create_user("owner-partial-active")
        StationStaff.objects.create(
            station=self.station_a,
            user=owner,
            role=StationStaff.ROLE_OWNER,
            is_active=True,
        )
        StationStaff.objects.create(
            station=self.station_b,
            user=owner,
            role=StationStaff.ROLE_OWNER,
            is_active=True,
        )
        StationStaff.objects.create(
            station=self.station_c,
            user=owner,
            role=StationStaff.ROLE_OWNER,
            is_active=False,
        )
        self.client.force_login(owner)

        response = self.client.get(reverse("station_select"))

        self.assertEqual(response.status_code, 200)
        station_ids = set(response.context["stations"].values_list("pk", flat=True))
        self.assertEqual(station_ids, {self.station_a.pk, self.station_b.pk})
        self.assertIn("_auth_user_id", self.client.session)

    def test_owner_is_logged_out_when_last_station_role_is_deactivated(self):
        owner = self.create_user("owner-disabled")
        StationStaff.objects.create(
            station=self.station_a,
            user=owner,
            role=StationStaff.ROLE_OWNER,
            is_active=False,
        )
        self.client.force_login(owner)

        response = self.client.get(reverse("station_select"))

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_station_password_page_is_for_staff_not_clients(self):
        operator = self.create_user("operator-password")
        StationStaff.objects.create(
            station=self.station_a,
            user=operator,
            role=StationStaff.ROLE_OPERATOR,
        )
        self.client.force_login(operator)

        response = self.client.get(reverse("station_change_password"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Смена пароля сотрудника")

        self.client.logout()
        client_user = self.create_user("client-no-station-password")
        self.client.force_login(client_user)
        response = self.client.get(reverse("station_change_password"))
        self.assertRedirects(response, reverse("cabinet"), fetch_redirect_response=False)

    def test_header_uses_active_station_account_mode(self):
        owner = self.create_user("owner-header")
        StationStaff.objects.create(
            station=self.station_a,
            user=owner,
            role=StationStaff.ROLE_OWNER,
        )
        self.client.force_login(owner)

        response = self.client.get(reverse("home"))

        self.assertContains(response, "Кабинет станции")
        self.assertNotContains(response, "Мои автомобили")

    def test_system_superuser_cannot_be_assigned_station_role(self):
        system_admin = User.objects.create_superuser(
            username="system-admin-not-staff",
            password=self.password,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Системный администратор не может одновременно быть сотрудником станции",
        ):
            StationStaff.objects.create(
                station=self.station_a,
                user=system_admin,
                role=StationStaff.ROLE_OWNER,
            )

    def test_station_account_cannot_be_promoted_to_superuser(self):
        owner = self.create_user("station-owner-not-admin")
        StationStaff.objects.create(
            station=self.station_a,
            user=owner,
            role=StationStaff.ROLE_OWNER,
        )

        owner.is_staff = True
        owner.is_superuser = True
        with self.assertRaisesMessage(
            ValidationError,
            "Системный администратор не может одновременно быть сотрудником станции",
        ):
            owner.save(update_fields=["is_staff", "is_superuser"])

        owner.refresh_from_db()
        self.assertFalse(owner.is_superuser)
