(function () {
    let map;
    let placemark = null;

    function init() {
        const latInput = document.getElementById("id_latitude");
        const lngInput = document.getElementById("id_longitude");
        const addressInput = document.getElementById("id_address");

        if (!latInput || !lngInput) {
            return;
        }

        const startLat = latInput.value ? parseFloat(latInput.value) : 55.751574;
        const startLng = lngInput.value ? parseFloat(lngInput.value) : 37.573856;

        map = new ymaps.Map("map", {
            center: [startLat, startLng],
            zoom: 12,
            controls: ["zoomControl", "searchControl"]
        });

        function setPlacemark(coords) {
            latInput.value = coords[0].toFixed(6);
            lngInput.value = coords[1].toFixed(6);

            if (!placemark) {
                placemark = new ymaps.Placemark(
                    coords,
                    {},
                    { draggable: true }
                );
                map.geoObjects.add(placemark);

                placemark.events.add("dragend", function () {
                    updateAddress(
                        placemark.geometry.getCoordinates()
                    );
                });
            } else {
                placemark.geometry.setCoordinates(coords);
            }

            updateAddress(coords);
        }

        function updateAddress(coords) {
            ymaps.geocode(coords).then(function (res) {
                const geoObject = res.geoObjects.get(0);
                if (!geoObject) return;

                const address = geoObject.getAddressLine();
                if (addressInput) {
                    addressInput.value = address;
                }
            });
        }

        // Если координаты уже есть (редактирование станции)
        if (latInput.value && lngInput.value) {
            setPlacemark([startLat, startLng]);
        }

        // Клик по карте
        map.events.add("click", function (e) {
            setPlacemark(e.get("coords"));
        });
    }

    ymaps.ready(init);
})();