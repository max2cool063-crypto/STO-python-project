from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from booking.account_access import require_active_station_account


@require_active_station_account
@require_http_methods(["GET", "POST"])
def station_change_password(request):
    """Change the password without exposing the client cabinet to staff accounts."""
    if request.method == "POST":
        current = request.POST.get("current_password", "")
        new_password = request.POST.get("new_password", "")
        confirmation = request.POST.get("confirm_password", "")

        if not request.user.check_password(current):
            messages.error(request, "Неверный текущий пароль")
            return redirect("station_change_password")
        if new_password != confirmation:
            messages.error(request, "Пароли не совпадают")
            return redirect("station_change_password")

        try:
            validate_password(new_password, request.user)
        except ValidationError as exc:
            for error in exc.messages:
                messages.error(request, error)
            return redirect("station_change_password")

        request.user.set_password(new_password)
        request.user.save(update_fields=["password"])
        update_session_auth_hash(request, request.user)
        messages.success(request, "Пароль успешно изменён")
        return redirect("station_select")

    return render(request, "booking/station/change_password.html")
