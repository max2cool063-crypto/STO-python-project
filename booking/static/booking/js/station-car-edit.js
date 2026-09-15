(function () {
  const dialog = document.getElementById('car-edit-dialog');
  const form = document.getElementById('car-edit-dialog-form');
  const error = document.getElementById('car-edit-error');
  const button = document.getElementById('edit-selected-car');
  const feedback = document.getElementById('car-info');
  let url = '';
  const letters = {A:'А',B:'В',E:'Е',K:'К',M:'М',H:'Н',O:'О',P:'Р',C:'С',T:'Т',Y:'У',X:'Х'};
  const normalizePlate = value => [...value.toUpperCase()].map(char => letters[char] || char).join('').trim();
  document.getElementById('car-edit-close').addEventListener('click', () => dialog.close());
  button.addEventListener('click', async () => {
    const carId = button.dataset.carId || (typeof currentCarId !== 'undefined' ? currentCarId : null);
    if (!carId) return;
    url = '/station/' + dialog.dataset.stationId + '/cars/' + carId + '/edit/';
    button.disabled = true;
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
      feedback.textContent = 'Не удалось открыть автомобиль. Повторите попытку.';
    } finally {
      button.disabled = false;
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
      document.dispatchEvent(new CustomEvent('station-car-saved', {detail: data}));
      dialog.close();
    } catch (_) {
      error.textContent = 'Не удалось сохранить автомобиль. Повторите попытку.';
    } finally {
      submit.disabled = false;
    }
  });
})();
