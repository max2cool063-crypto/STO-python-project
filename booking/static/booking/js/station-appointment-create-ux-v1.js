(function () {
  const dateInput = document.getElementById('date-input');
  const modelSelect = document.getElementById('model-select');
  if (!dateInput || !modelSelect || typeof STATION_ID === 'undefined' || typeof loadSlots !== 'function') return;

  function selectedVehicleType() {
    if (typeof currentCarId !== 'undefined' && currentCarId) return '';
    const option = modelSelect.selectedOptions && modelSelect.selectedOptions[0];
    return option && option.value ? (option.dataset.vehicleType || '') : '';
  }

  loadSlots = async function (date) {
    const native = document.getElementById('slots-select');
    const chips = document.getElementById('slot-chips');
    const hint = document.getElementById('slots-hint');
    const count = document.getElementById('slots-count');
    const summaryTime = document.getElementById('summary-time');

    native.innerHTML = '<option value="">Выберите время</option>';
    chips.innerHTML = '<div class="st-slot-placeholder">Загрузка слотов…</div>';
    count.textContent = '';
    summaryTime.textContent = 'Не выбрано';

    if (!date) {
      setProgressState();
      return;
    }

    let url = '/api/station/' + STATION_ID + '/slots/?date=' + encodeURIComponent(date);
    if (typeof currentCarId !== 'undefined' && currentCarId) {
      url += '&car=' + encodeURIComponent(currentCarId);
    } else {
      const vehicleType = selectedVehicleType();
      if (vehicleType) url += '&vehicle_type=' + encodeURIComponent(vehicleType);
    }

    try {
      const response = await fetch(url);
      const data = await response.json();
      chips.innerHTML = '';

      if (!data.slots || !data.slots.length) {
        chips.innerHTML = '<div class="st-slot-placeholder">Нет свободных слотов на эту дату</div>';
        hint.textContent = 'Попробуйте выбрать другой день';
        setProgressState();
        return;
      }

      hint.textContent = '';
      count.textContent = 'Найдено: ' + data.slots.length;
      data.slots.forEach(function (slot) {
        const start = slot.start;
        const end = slot.end;
        const startTime = start.substring(11, 16);
        const endTime = end.substring(11, 16);

        const option = document.createElement('option');
        option.value = start;
        option.textContent = startTime + ' — ' + endTime;
        native.appendChild(option);

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'st-slot-chip';
        button.textContent = startTime + ' — ' + endTime;
        button.addEventListener('click', function () {
          document.querySelectorAll('.st-slot-chip').forEach(function (item) {
            item.classList.remove('is-selected');
          });
          button.classList.add('is-selected');
          native.value = start;
          summaryTime.textContent = startTime + ' — ' + endTime;
          setProgressState();
        });
        chips.appendChild(button);
      });
    } catch (error) {
      chips.innerHTML = '<div class="st-slot-placeholder">Не удалось загрузить слоты</div>';
      hint.textContent = 'Попробуйте ещё раз';
      setProgressState();
    }
  };

  modelSelect.addEventListener('change', function () {
    if (dateInput.value) loadSlots(dateInput.value);
  });
})();
