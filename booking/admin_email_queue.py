from django.contrib import admin
from django.utils import timezone

from booking.models import EmailOutbox


@admin.register(EmailOutbox)
class EmailOutboxAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "status", "attempts", "created_at", "available_at", "last_error")
    list_filter = ("status", "kind")
    search_fields = ("=id",)
    fields = ("id", "kind", "status", "attempts", "created_at", "available_at", "finished_at", "last_error", "appointment", "user")
    readonly_fields = fields
    actions = ("retry_failed",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Повторить отправку писем с исчерпанными попытками")
    def retry_failed(self, request, queryset):
        count = queryset.filter(status="failed").update(status="pending", attempts=0,
            available_at=timezone.now(), finished_at=None, last_error="", lock_token=None, locked_until=None)
        self.message_user(request, f"Возвращено в очередь: {count}. Актуальность будет проверена перед отправкой.")
