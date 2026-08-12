from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "POST"])
def register(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        if not email:
            messages.error(request, "Введите email")
            return redirect("register")

        if "@" not in email or "." not in email.split("@")[-1]:
            messages.error(request, "Некорректный формат email")
            return redirect("register")

        if User.objects.filter(email=email).exists():
            # FIX: не раскрываем факт регистрации email — защита от перебора
            messages.success(request, "Если email существует, пароль будет отправлен")
            return redirect("login")

        # FIX: 12 символов вместо 8 для большей стойкости пароля
        password = get_random_string(12)

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password
        )

        body = "Ваш пароль: " + password + "\nВход: " + email + "\n\nРекомендуем сменить пароль после первого входа."
        try:
            send_mail(
                "Доступ к сервису СТО",
                body,
                None,
                [email],
                fail_silently=False,
            )
        except Exception:
            user.delete()
            messages.error(request, "Ошибка отправки письма. Попробуйте позже.")
            return redirect("register")

        messages.success(request, "Пароль отправлен на вашу почту")
        return redirect("login")

    return render(request, "registration/register.html")


from django.contrib.auth.decorators import login_required

@login_required
def post_login_redirect(request):
    """
    Умный редирект после входа:
    - Сотрудник станции → кабинет станции (или выбор если несколько)
    - Обычный пользователь → клиентский кабинет
    """
    from booking.models import StationStaff
    from booking.station_access import get_user_stations

    stations = get_user_stations(request.user)
    if stations.exists():
        if stations.count() == 1:
            from django.urls import reverse
            return redirect(reverse("station_dashboard", kwargs={"station_id": stations.first().pk}))
        return redirect("station_select")
    return redirect("cabinet")
