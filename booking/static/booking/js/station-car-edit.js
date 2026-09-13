(function () {
  const dialog = document.getElementById('car-edit-dialog');
  const form = document.getElementById('car-edit-dialog-form');
  const error = document.getElementById('car-edit-error');
  let url = '';
  document.getElementById('car-edit-close').addEventListener('click', () => dialog.close());
  document.getElementById('edit-selected-car').addEventListener('click', async () => {
    if (!currentCarId) return;
    url = '/station/' + STATION_ID + '/cars/' + currentCarId + '/edit/';
    error.textContent = '';
    try {
      const response = await fetch(url, {headers: {Accept: 'application/json'}});
      if (!response.ok) throw new Error();
      const car = await response.json();
      form.elements.plate_number.value = car.plate_number;
      form.elements.vin.value = car.vin;
      form.elements.vehicle_type.value = car.vehicle_type;
      dialog.showModal();
    } catch (_) {
      document.getElementById('car-info').textContent = 'Не удалось открыть автомобиль. Повторите попытку.';
    }
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    error.textContent = '';
    form.elements.plate_number.value = normalizePlate(form.elements.plate_number.value);
    form.elements.vin.value = form.elements.vin.value.trim().toUpperCase();
    try {
      const response = await fetch(url, {method: 'POST', body: new FormData(form), headers: {Accept: 'application/json'}});
      const data = await response.json();
      if (!response.ok) {
        error.textContent = data.errors ? Object.values(data.errors).flat().map(item => item.message).join(' ') : 'Не удалось сохранить автомобиль.';
        return;
      }
      document.getElementById('plate-input').value = form.elements.plate_number.value;
      updateDurationSummary(form.elements.vehicle_type.value);
      document.getElementById('car-info').textContent = 'Автомобиль сохранён. Выберите свободное время заново.';
      const date = document.getElementById('date-input').value;
      await loadSlots(date);
      dialog.close();
    } catch (_) {
      error.textContent = 'Не удалось сохранить автомобиль. Повторите попытку.';
    } finally {
      submit.disabled = false;
    }
  });
})();
