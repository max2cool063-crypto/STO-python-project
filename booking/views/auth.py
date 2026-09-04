from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_http_methods
from django.contrib.auth.views import LoginView
from django.core.cache import cache

from booking.security import LOGIN_RATE_LIMIT, REGISTRATION_RATE_LIMIT

User = get_user_model()


def send_password_setup_email(request, user):
    """Send a one-time password setup/reset link; never put a password in email."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    setup_url = request.build_absolute_uri(
        reverse("set_password", kwargs={"uidb64": uid, "token": token})
    )
    return send_mail(
        "Установите или сбросьте пароль для сервиса СТО",
        (
            "Для вашего аккаунта в сервисе СТО можно установить новый пароль.\n\n"
            f"Перейдите по ссылке: {setup_url}\n\n"
            "Ссылка одноразовая и действует ограниченное время."
        ),
        None,
        [user.email],
        fail_silently=False,
    )


@require_http_methods(["GET", "POST"])
def register(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        if not REGISTRATION_RATE_LIMIT.allowed(request):
            return REGISTRATION_RATE_LIMIT.retry_response()
        REGISTRATION_RATE_LIMIT.hit(request)

        if not email:
            messages.error(request, "Введите email")
            return redirect("register")

        if "@" not in email or "." not in email.split("@")[-1]:
            messages.error(request, "Некорректный формат email")
            return redirect("register")

        user = User.objects.filter(email__iexact=email).order_by("id").first()
        if user:
            # Не раскрываем факт существования аккаунта. Повторная отправка
            # ссылки работает и для уже активированного аккаунта, поэтому
            # пользователь может самостоятельно восстановить забытый пароль.
            try:
                send_password_setup_email(request, user)
            except Exception:
                pass
            messages.success(request, "Если email существует, инструкция будет отправлена на почту")
            return redirect("login")

        user = User.objects.create_user(
            username=email,
            email=email,
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])

        try:
            send_password_setup_email(request, user)
        except Exception:
            user.delete()
            messages.error(request, "Ошибка отправки письма. Попробуйте позже.")
            return redirect("register")

        messages.success(request, "Инструкция для установки пароля отправлена на вашу почту")
        return redirect("login")

    return render(request, "registration/register.html")


@require_http_methods(["GET", "POST"])
def set_password(request, uidb64, token):
    """One-time password setup/reset link."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if not user or not default_token_generator.check_token(user, token):
        messages.error(request, "Ссылка недействительна или уже использована")
        return redirect("login")

    if request.method == "POST":
        password = request.POST.get("password", "")
        confirmation = request.POST.get("confirmation", "")

        if password != confirmation:
            messages.error(request, "Пароли не совпадают")
            return render(request, "registration/set_password.html")

        try:
            validate_password(password, user)
        except ValidationError as exc:
            for error in exc.messages:
                messages.error(request, error)
            return render(request, "registration/set_password.html")

        user.set_password(password)
        user.save(update_fields=["password"])
        messages.success(request, "Пароль установлен. Теперь можно войти в систему.")
        return redirect("login")

    return render(request, "registration/set_password.html")


class RateLimitedLoginView(LoginView):
    """Django login view with a cache-backed failed-attempt limit."""

    template_name = "registration/login.html"

    def post(self, request, *args, **kwargs):
        identity = request.POST.get("username", "")
        if not LOGIN_RATE_LIMIT.allowed(request, identity):
            return LOGIN_RATE_LIMIT.retry_response()
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        identity = self.request.POST.get("username", "")
        LOGIN_RATE_LIMIT.hit(self.request, identity)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(LOGIN_RATE_LIMIT._key(self.request, self.request.POST.get("username", "")))
        return super().form_valid(form)


@login_required
def post_login_redirect(request):
    """
    Умный редирект после входа:
    - Сотрудник станции → кабинет станции (или выбор если несколько)
    - Обычный пользователь → клиентский кабинет
    """
    from booking.station_access import get_user_stations

    stations = get_user_stations(request.user)
    if stations.exists():
        if stations.count() == 1:
            return redirect(reverse("station_dashboard", kwargs={"station_id": stations.first().pk}))
        return redirect("station_select")
    return redirect("cabinet")
