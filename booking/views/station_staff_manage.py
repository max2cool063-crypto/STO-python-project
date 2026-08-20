from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from booking.models import StationStaff, UserProfile
from booking.station_access import require_station_access

User = get_user_model()


@login_required
@require_station_access(role=StationStaff.ROLE_OWNER)
def station_staff_create_operator(request, station_id, staff=None):
    station = staff.station
    if request.method != "POST":
        return redirect("station_staff", station_id=station_id)

    login = request.POST.get("login", "").strip()
    password = request.POST.get("password", "")
    email = request.POST.get("email", "").strip().lower()
    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()

    if not login:
        messages.error(request, "Укажите логин для оператора")
        return redirect(request.META.get("HTTP_REFERER") or "station_staff", station_id=station_id)
    if User.objects.filter(username=login).exists():
        messages.error(request, f"Логин «{login}» уже занят, выберите другой")
        return redirect("station_staff", station_id=station_id)
    if email and User.objects.filter(email__iexact=email).exists():
        messages.error(request, "Пользователь с таким email уже существует")
        return redirect("station_staff", station_id=station_id)

    try:
        validate_password(password)
    except ValidationError as exc:
        for error in exc.messages:
            messages.error(request, error)
        return redirect("station_staff", station_id=station_id)

    with transaction.atomic():
        user = User.objects.create_user(username=login, email=email, password=password)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.first_name = first_name
        profile.last_name = last_name
        profile.save(update_fields=["first_name", "last_name"])
        StationStaff.objects.create(
            station=station,
            user=user,
            role=StationStaff.ROLE_OPERATOR,
            created_by=request.user,
        )

    if email:
        try:
            send_mail(
                "Доступ к кабинету станции СТО",
                (
                    f"Вам создан аккаунт оператора станции «{station.name}».\n\n"
                    f"Имя: {first_name} {last_name}\n"
                    f"Логин: {login}\n"
                    "Пароль передайте оператору безопасным способом."
                ),
                None,
                [email],
                fail_silently=True,
            )
        except Exception:
            pass

    messages.success(request, f"Оператор «{login}» создан")
    return redirect("station_staff", station_id=station_id)


@login_required
@require_station_access(role=StationStaff.ROLE_OWNER)
@require_http_methods(["GET", "POST"])
def station_staff_edit_profile(request, station_id, member_id, staff=None):
    station = staff.station
    member = get_object_or_404(
        StationStaff.objects.select_related("user__profile"),
        pk=member_id,
        station=station,
    )

    # Владелец может редактировать себя и операторов своей станции.
    # Другого владельца станции редактировать через этот интерфейс нельзя.
    if member.user_id != request.user.id and member.role != StationStaff.ROLE_OPERATOR:
        messages.error(request, "Редактирование этого профиля недоступно")
        return redirect("station_staff", station_id=station_id)

    profile, _ = UserProfile.objects.get_or_create(user=member.user)

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        phone = request.POST.get("phone", "").strip()

        if email and User.objects.filter(email__iexact=email).exclude(pk=member.user_id).exists():
            messages.error(request, "Этот email уже используется другим пользователем")
            return redirect(request.path)

        member.user.email = email
        member.user.save(update_fields=["email"])
        profile.first_name = first_name
        profile.last_name = last_name
        profile.phone = phone
        profile.save(update_fields=["first_name", "last_name", "phone"])

        messages.success(request, f"Профиль «{member.user.username}» сохранён")
        return redirect("station_staff", station_id=station_id)

    return render(request, "booking/station/staff_profile_edit.html", {
        "station": station,
        "staff": staff,
        "member": member,
        "profile": profile,
    })
