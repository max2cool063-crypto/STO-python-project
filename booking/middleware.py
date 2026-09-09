from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import Resolver404, resolve

from booking.account_access import (
    DEACTIVATED_STAFF_MESSAGE,
    STAFF_ONLY_MESSAGE,
    get_station_account_state,
)


class StationAccountAccessMiddleware:
    """Enforce the permanent separation between client and station accounts."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.has_station_account = False
        request.has_active_station_access = False

        if request.user.is_authenticated:
            has_staff_history, has_active_role = get_station_account_state(request.user)
            request.has_station_account = has_staff_history
            request.has_active_station_access = has_active_role

            # A staff identity stays a staff identity after deactivation. Once
            # its last active role is disabled, any existing session is revoked.
            if has_staff_history and not has_active_role:
                logout(request)
                messages.error(request, DEACTIVATED_STAFF_MESSAGE)
                return redirect("login")

            if has_active_role and self._is_client_only_request(request):
                messages.error(request, STAFF_ONLY_MESSAGE)
                return redirect("station_select")

        return self.get_response(request)

    @staticmethod
    def _is_client_only_request(request):
        path = request.path_info or ""
        if path == "/cabinet" or path.startswith("/cabinet/"):
            return True

        try:
            match = resolve(path)
        except Resolver404:
            return False
        return match.url_name == "book_station"
