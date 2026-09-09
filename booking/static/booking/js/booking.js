(function () {
  if (
    typeof loadSlots !== 'function' ||
    typeof selectedSlot === 'undefined' ||
    typeof STATION_ID === 'undefined'
  ) {
    return;
  }

  const dateField = document.getElementById('date');
  const slotsContainer = document.getElementById('slots');
  const carField = document.getElementById('car-select');
  const bookingFormElement = document.getElementById('booking-form');
  const selectedInfo = document.getElementById('selected-slot-info');
  const slotDisplay = document.getElementById('slot-display');
  const startField = document.getElementById('start');
  const endField = document.getElementById('end');
  const slotsCount = document.getElementById('slots-count');
  const submitButton = document.getElementById('submit-btn');

  if (
    !dateField || !slotsContainer || !carField || !bookingFormElement ||
    !selectedInfo || !slotDisplay || !startField || !endField || !slotsCount ||
    !submitButton
  ) {
    return;
  }

  const timePart = (value) => value ? value.slice(11, 16) : '';

  function updateSelectedSlot(slot) {
    selectedSlot = slot;
    startField.value = slot.start;
    endField.value = slot.end;
    bookingFormElement.style.display = 'block';
    selectedInfo.style.display = 'flex';
    slotDisplay.textContent =
      new Date(slot.start).toLocaleDateString('ru-RU', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
      }) + ', ' + timePart(slot.start) + ' – ' + timePart(slot.end);

    if (typeof setStepState === 'function') setStepState();
    if (typeof updateSubmit === 'function') updateSubmit();
  }

  function clearSelectedSlot() {
    selectedSlot = null;
    startField.value = '';
    endField.value = '';
    selectedInfo.style.display = 'none';
    bookingFormElement.style.display = 'none';
    document.getElementById('step-car')?.classList.remove('is-active');
    document.getElementById('step-confirm')?.classList.remove('is-active');
    if (typeof updateSubmit === 'function') updateSubmit();
  }

  loadSlots = function () {
    if (!dateField.value) return;

    submitButton.disabled = true;
    slotsContainer.innerHTML = '<span class="booking-loading">Загрузка доступных слотов…</span>';
    const carParam = carField.value ? '&car=' + encodeURIComponent(carField.value) : '';

    fetch('/api/station/' + STATION_ID + '/slots/?date=' + encodeURIComponent(dateField.value) + carParam)
      .then((response) => response.json())
      .then((data) => {
        const slots = Array.isArray(data.slots) ? data.slots : [];
        slotsContainer.innerHTML = '';
        slotsCount.textContent = slots.length ? 'Доступно: ' + slots.length : '';

        if (!slots.length) {
          slotsContainer.innerHTML = '<span class="booking-empty-slots">На эту дату нет свободных слотов</span>';
          if (selectedSlot) clearSelectedSlot();
          return;
        }

        const refreshedSelected = selectedSlot
          ? slots.find((slot) => slot.start === selectedSlot.start)
          : null;

        slots.forEach((slot) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'slot';
          button.textContent = timePart(slot.start);

          if (refreshedSelected && refreshedSelected.start === slot.start) {
            button.classList.add('slot-selected');
          }

          button.addEventListener('click', () => {
            document.querySelectorAll('.slot-selected').forEach((element) => {
              element.classList.remove('slot-selected');
            });
            button.classList.add('slot-selected');
            updateSelectedSlot(slot);
            bookingFormElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
          });

          slotsContainer.appendChild(button);
        });

        if (selectedSlot) {
          if (refreshedSelected) {
            // The same start time can have a different end after the user chooses
            // a vehicle. For example, a truck changes 08:30–09:00 to 08:30–09:30.
            updateSelectedSlot(refreshedSelected);
          } else {
            // The previously selected start may no longer fit a truck because the
            // following 30-minute slot is occupied. Require a new valid selection.
            clearSelectedSlot();
          }
        } else if (typeof updateSubmit === 'function') {
          updateSubmit();
        }
      })
      .catch(() => {
        slotsContainer.innerHTML = '<span class="booking-empty-slots">Не удалось загрузить слоты. Попробуйте ещё раз.</span>';
        slotsCount.textContent = '';
        submitButton.disabled = true;
      });
  };
})();
