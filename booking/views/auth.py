import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from booking.email_queue import enqueue_mail as send_mail
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_http_methods
from django.contrib.auth.views import LoginView
from django.core.cache import cache

from booking.account_access import DEACTIVATED_STAFF_MESSAGE, get_station_account_state
from booking.security import LOGIN_IP_RATE_LIMIT, LOGIN_RATE_LIMIT, REGISTRATION_RATE_LIMIT
from booking.input_validation import validate_user_fields

logger = logging.getLogger(__name__)
User = get_user_model()
REGISTRATION_RESPONSE_MESSAGE = (
    "Если адрес можно использовать, инструкция будет отправлена на почту"
)


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
        kind="password", user=user, auth_token=token,
        expires_at=timezone.now() + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT),
    )


def _finish_registration_request(request, user, *, delete_on_mail_failure=False):
    """Send the setup link while keeping registration responses non-enumerating."""
    try:
        send_password_setup_email(request, user)
    except Exception:
        if delete_on_mail_failure:
            user.delete()
        logger.exception("Failed to send password setup email during registration")
        messages.error(request, "Не удалось отправить письмо. Попробуйте позже.")
        return redirect("login")

    messages.success(request, REGISTRATION_RESPONSE_MESSAGE)
    return redirect("login")


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

        try:
            validate_email(email)
            validate_user_fields(email=email)
        except ValidationError:
            messages.error(request, "Некорректный формат email")
            return redirect("register")

        user = User.objects.filter(email__iexact=email).order_by("id").first()
        if user:
            return _finish_registration_request(request, user)

        try:
            # Email local-parts allow characters that Django's username regex
            # rejects. Preserve existing email login support; constrain length.
            MaxLengthValidator(User._meta.get_field("username").max_length)(email)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("register")

        # Client accounts use the normalized email as the Django username. If
        # that username was historically assigned to a different identity (for
        # example a station operator whose email field is blank), do not crash
        # with a uniqueness error and do not reveal the collision to the caller.
        if User.objects.filter(username=email).exists():
            logger.warning("Registration username collision for normalized email")
            messages.success(request, REGISTRATION_RESPONSE_MESSAGE)
            return redirect("login")

        try:
            with transaction.atomic():
                user = User.objects.create_user(username=email, email=email)
                user.set_unusable_password()
                user.save(update_fields=["password"])
                return _finish_registration_request(request, user, delete_on_mail_failure=True)
        except IntegrityError:
            # Two public registration requests for the same new address can pass
            # the initial lookup concurrently. The unique username is the final
            # arbiter; after the winning transaction commits, reuse that account.
            user = User.objects.filter(
                username=email,
                email__iexact=email,
            ).first()
            if user is None:
                logger.warning("Registration identity collision could not be reused")
                messages.success(request, REGISTRATION_RESPONSE_MESSAGE)
                return redirect("login")
            return _finish_registration_request(request, user)

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
    """Django login view with cache-backed per-identity and per-IP limits."""

    template_name = "registration/login.html"

    def post(self, request, *args, **kwargs):
        identity = request.POST.get("username", "")
        if not LOGIN_IP_RATE_LIMIT.allowed(request):
            return LOGIN_IP_RATE_LIMIT.retry_response()
        if not LOGIN_RATE_LIMIT.allowed(request, identity):
            return LOGIN_RATE_LIMIT.retry_response()
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        identity = self.request.POST.get("username", "")
        LOGIN_RATE_LIMIT.hit(self.request, identity)
        LOGIN_IP_RATE_LIMIT.hit(self.request)
        return super().form_invalid(form)

    def form_valid(self, form):
        user = form.get_user()
        has_staff_history, has_active_role = get_station_account_state(user)
        if has_staff_history and not has_active_role:
            form.add_error(None, DEACTIVATED_STAFF_MESSAGE)
            return self.render_to_response(self.get_context_data(form=form))

        # A successful login clears only the identity-specific failure bucket.
        # Aggregate IP failures are retained so an attacker cannot reset a broad
        # credential-stuffing budget by successfully logging into one account.
        cache.delete(LOGIN_RATE_LIMIT._key(self.request, self.request.POST.get("username", "")))
        return super().form_valid(form)


@login_required
def post_login_redirect(request):
    """
    Умный редирект после входа:
    - Активный сотрудник станции → кабинет станции (или выбор если несколько)
    - Деактивированный сотрудник → выход из сессии
    - Обычный пользователь → клиентский кабинет
    """
    from booking.station_access import get_user_stations

    has_staff_history, has_active_role = get_station_account_state(request.user)
    if has_staff_history:
        if not has_active_role:
            logout(request)
            messages.error(request, DEACTIVATED_STAFF_MESSAGE)
            return redirect("login")

        stations = get_user_stations(request.user)
        if stations.count() == 1:
            return redirect(reverse("station_dashboard", kwargs={"station_id": stations.first().pk}))
        return redirect("station_select")

    return redirect("cabinet")
