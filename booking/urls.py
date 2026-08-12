from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from booking.views.api import brands_api, models_api, station_slots_api, car_api, car_by_plate_api, brands_with_models_api

urlpatterns = [
    # ПУБЛИЧНЫЙ ФРОНТ
    path("", views.station_list, name="home"),

    # API
    path("api/stations/", views.stations_json, name="stations_json"),
    path("api/station/<int:station_id>/slots/", station_slots_api, name="station_slots_api"),
    path("api/brands/", brands_api, name="brands_api"),
    path("api/models/<int:brand_id>/", models_api, name="models_api"),
    path("api/cars/<int:car_id>/", car_api, name="car_api"),
    path("api/car-by-plate/", car_by_plate_api, name="car_by_plate_api"),
    path("api/brands-with-models/", brands_with_models_api, name="brands_with_models_api"),

    # ОНЛАЙН ЗАПИСЬ
    path("station/<int:pk>/book/", views.book_station, name="book_station"),

    # ЛИЧНЫЙ КАБИНЕТ КЛИЕНТА
    path("cabinet/", views.cabinet_dashboard, name="cabinet"),
    path("cabinet/cars/", views.cabinet_cars, name="cabinet_cars"),
    path("cabinet/cars/<int:pk>/edit/", views.cabinet_car_edit, name="cabinet_car_edit"),
    path("cabinet/cars/<int:pk>/delete/", views.cabinet_car_delete, name="cabinet_car_delete"),
    path("cabinet/appointments/", views.cabinet_appointments, name="cabinet_appointments"),
    path("cabinet/appointments/<int:pk>/cancel/", views.cabinet_cancel_appointment, name="cabinet_cancel_appointment"),
    path("cabinet/appointments/<int:pk>/photos.zip/", views.appointment_photos_zip, name="appointment_photos_zip"),

    # FIX: защищённая отдача фото записей — только для владельца
    path("media/appointments/<path:path>", views.protected_media, name="protected_media"),

    # AUTH
    path("accounts/register/", views.register, name="register"),
    path("accounts/post-login/", views.post_login_redirect, name="post_login_redirect"),
    path("cabinet/password/", views.change_password, name="change_password"),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),

    # КАБИНЕТ СТАНЦИИ
    path("station/", views.station_select, name="station_select"),
    path("station/<int:station_id>/", views.station_dashboard, name="station_dashboard"),
    path("station/<int:station_id>/appointments/", views.station_appointments, name="station_appointments"),
    path("station/<int:station_id>/appointments/create/", views.station_appointment_create, name="station_appointment_create"),
    path("station/<int:station_id>/appointments/<int:pk>/status/", views.station_appointment_status, name="station_appointment_status"),
    path("station/<int:station_id>/appointments/<int:pk>/", views.station_appointment_detail, name="station_appointment_detail"),
    path("station/<int:station_id>/appointments/csv/", views.station_appointments_csv, name="station_appointments_csv"),
    path("station/<int:station_id>/schedule/", views.station_schedule, name="station_schedule"),
    path("station/<int:station_id>/slot-blocks/", views.station_slot_blocks, name="station_slot_blocks"),
    path("station/<int:station_id>/clients/", views.station_clients, name="station_clients"),
    path("station/<int:station_id>/staff/", views.station_staff, name="station_staff"),
]
