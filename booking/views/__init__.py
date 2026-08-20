from .public import station_list, stations_json
from .booking import book_station
from .auth import register, post_login_redirect, set_password
from .cabinet import (
    change_password,
    cabinet_dashboard,
    cabinet_cars,
    cabinet_car_edit,
    cabinet_car_delete,
    cabinet_appointments,
    cabinet_cancel_appointment,
    appointment_photos_zip,
    protected_media,
)
from .station_appointment_create import station_appointment_create
from .station_appointment_detail import station_appointment_detail
from .station_cabinet import (
    station_select,
    station_dashboard,
    station_appointments,
    station_appointment_status,
    station_appointments_csv,
    station_schedule,
    station_slot_blocks,
    station_clients,
    station_staff,
)
