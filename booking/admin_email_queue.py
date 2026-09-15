from django.contrib import admin
from django.utils import timezone

from booking.models import EmailOutbox


@admin.register(EmailOutbox)
class EmailOutboxAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "status", "attempts", "created_at", "available_at", "last_error_display")
    list_filter = ("status", "kind")
    search_fields = ("=id",)
    fields = ("id", "kind", "status", "attempts", "created_at", "available_at", "finished_at", "last_error_display", "appointment", "user")
    readonly_fields = fields
    actions = ("retry_failed",)

    @admin.display(description="Последняя ошибка", ordering="last_error")
    def last_error_display(self, obj):
        descriptions = {
            "WorkerLeaseExpired": "Истекло время обработки письма",
            "Expired": "Истёк срок действия письма",
            "AccountChanged": "Учётная запись или адрес получателя изменены",
            "PasswordLinkInvalid": "Ссылка для установки пароля недействительна",
            "StaffDeactivated": "Доступ сотрудника отключён",
            "AppointmentDeleted": "Запись на ТО удалена",
            "AppointmentChanged": "Время или статус записи изменены, письмо устарело",
            "StaffRecipientChanged": "Доступ, адрес или настройки уведомлений сотрудника изменены",
            "ClientRecipientChanged": "Доступ или адрес клиента изменены",
            "ConnectionError": "Ошибка подключения к почтовому серверу",
            "ConnectionRefusedError": "Почтовый сервер отклонил подключение",
            "ConnectionResetError": "Соединение с почтовым сервером сброшено",
            "ConnectionAbortedError": "Соединение с почтовым сервером прервано",
            "BrokenPipeError": "Соединение прервано во время отправки",
            "TimeoutError": "Истекло время ожидания ответа почтового сервера",
            "gaierror": "Не удалось определить адрес почтового сервера",
            "SMTPAuthenticationError": "Почтовый сервер отклонил авторизацию",
            "SMTPRecipientsRefused": "Почтовый сервер отклонил получателя",
            "SMTPSenderRefused": "Почтовый сервер отклонил отправителя",
            "SMTPDataError": "Почтовый сервер отклонил содержимое письма",
            "SMTPConnectError": "Не удалось подключиться к почтовому серверу",
            "SMTPServerDisconnected": "Почтовый сервер разорвал соединение",
            "SMTPHeloError": "Ошибка согласования соединения с почтовым сервером",
            "SMTPNotSupportedError": "Почтовый сервер не поддерживает требуемую команду",
            "SMTPResponseException": "Почтовый сервер вернул ошибку",
            "SMTPException": "Ошибка обмена с почтовым сервером",
            "SSLError": "Ошибка защищённого соединения с почтовым сервером",
            "SSLCertVerificationError": "Не удалось проверить сертификат почтового сервера",
            "OSError": "Системная ошибка при отправке письма",
            "RuntimeError": "Внутренняя ошибка при отправке письма",
        }
        if not obj.last_error:
            return "Нет ошибок"
        return descriptions.get(obj.last_error, f"Ошибка отправки (код: {obj.last_error})")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Повторить отправку писем с исчерпанными попытками")
    def retry_failed(self, request, queryset):
        count = queryset.filter(status="failed").update(status="pending", attempts=0,
            available_at=timezone.now(), finished_at=None, last_error="", lock_token=None, locked_until=None)
        self.message_user(request, f"Возвращено в очередь: {count}. Актуальность будет проверена перед отправкой.")
