from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class VehicleTypeMigrationTests(TransactionTestCase):
    def test_existing_cars_including_inactive_keep_their_type(self):
        old = [("booking", "0028_email_schedule_revision")]
        new = [("booking", "0029_car_vehicle_type")]
        executor = MigrationExecutor(connection)
        executor.migrate(old)
        try:
            apps = executor.loader.project_state(old).apps
            user = apps.get_model("auth", "User").objects.create(username="migration-client")
            brand = apps.get_model("booking", "Brand").objects.create(name="Migration brand")
            CarModel = apps.get_model("booking", "CarModel")
            Car = apps.get_model("booking", "Car")
            passenger = CarModel.objects.create(brand=brand, name="Passenger", vehicle_type="CAR")
            truck = CarModel.objects.create(brand=brand, name="Truck", vehicle_type="TRUCK")
            ids = []
            for model, active in [(passenger, True), (truck, True), (truck, False)]:
                ids.append(Car.objects.create(owner=user, model=model, plate_number="А123ВС77", is_active=active).pk)
            executor = MigrationExecutor(connection)
            executor.migrate(new)
            apps = executor.loader.project_state(new).apps
            Car = apps.get_model("booking", "Car")
            self.assertEqual([Car.objects.get(pk=pk).vehicle_type for pk in ids], ["CAR", "TRUCK", "TRUCK"])
            self.assertNotIn("vehicle_type", [f.name for f in apps.get_model("booking", "CarModel")._meta.fields])
        finally:
            MigrationExecutor(connection).migrate(new)
