from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from booking.models import Notification


@login_required
@require_GET
def station_notifications(request):
    """Возвращает только непрочитанные уведомления текущего сотрудника для верхней панели."""
    notifications = (
        Notification.objects
        .filter(recipient=request.user, is_read=False)
        .select_related("appointment", "station")[:20]
    )
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    items = []
    for item in notifications:
        items.append({
            "id": item.id,
            "title": item.title,
            "message": item.message,
            "is_read": item.is_read,
            "created_at": item.created_at.isoformat(),
            "appointment_url": (
                f"/station/{item.station_id}/appointments/{item.appointment_id}/"
                if item.appointment_id else ""
            ),
        })
    return JsonResponse({"unread_count": unread_count, "notifications": items})


@login_required
@require_GET
def station_notifications_history(request):
    """Полная история уведомлений текущего сотрудника с фильтром по прочитанности."""
    filter_value = request.GET.get("filter", "all")
    notifications = (
        Notification.objects
        .filter(recipient=request.user)
        .select_related("appointment", "station")
    )
    if filter_value == "unread":
        notifications = notifications.filter(is_read=False)
    elif filter_value == "read":
        notifications = notifications.filter(is_read=True)

    return render(request, "booking/station/notifications.html", {
        "notifications": notifications[:100],
        "filter_value": filter_value,
        "unread_count": Notification.objects.filter(recipient=request.user, is_read=False).count(),
    })


@login_required
@require_POST
def station_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    if notification.appointment_id:
        return redirect("station_appointment_detail", station_id=notification.station_id, pk=notification.appointment_id)
    return redirect("station_dashboard", station_id=notification.station_id)


@login_required
@require_POST
def station_notifications_read_all(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"ok": True})
