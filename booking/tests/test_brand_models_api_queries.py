import json

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from booking.models import Brand, CarModel, Station, StationStaff
from booking.views.api import brands_with_models_api


class BrandModelsApiQueryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="catalog-operator")
        self.station = Station.objects.create(name="Catalog station")
        StationStaff.objects.create(
            station=self.station,
            user=self.user,
            role=StationStaff.ROLE_OPERATOR,
        )
        first = Brand.objects.create(name="Beta")
        second = Brand.objects.create(name="Alpha")
        CarModel.objects.create(brand=first, name="Zeta", vehicle_type="CAR")
        CarModel.objects.create(brand=first, name="Alpha", vehicle_type="TRUCK")
        CarModel.objects.create(brand=second, name="Gamma", vehicle_type="CAR")
        self.factory = RequestFactory()

    def test_catalog_uses_one_prefetch_query_for_all_models(self):
        request = self.factory.get("/api/brands-with-models/")
        request.user = self.user

        with self.assertNumQueries(3):
            response = brands_with_models_api(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual([brand["name"] for brand in payload], ["Alpha", "Beta"])
        beta = payload[1]
        self.assertEqual(
            [model["name"] for model in beta["models"]],
            ["Alpha", "Zeta"],
        )
