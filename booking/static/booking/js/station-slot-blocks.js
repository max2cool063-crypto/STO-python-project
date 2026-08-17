(function () {
  const form = document.querySelector('[data-slot-block-form]');
  if (!form) return;

  const date = document.getElementById('block-date');
  const start = document.getElementById('block-start-sel');
  const end = document.getElementById('block-end-sel');
  const startHidden = document.getElementById('start-hidden');
  const endHidden = document.getElementById('end-hidden');
  const title = document.getElementById('preview-title');
  const text = document.getElementById('preview-text');

  function updatePreview() {
    if (date.value && start.value && end.value && start.value < end.value) {
      const parts = date.value.split('-');
      title.textContent = `${parts[2]}.${parts[1]}.${parts[0]} · ${start.value} — ${end.value}`;
      text.textContent = 'Выбранный период будет недоступен для новой онлайн-записи.';
    } else {
      title.textContent = 'Период не выбран';
      text.textContent = 'Выберите дату и корректное время начала и конца.';
    }
  }

  [date, start, end].forEach((element) => element.addEventListener('change', updatePreview));

  form.addEventListener('submit', function (event) {
    if (!date.value) {
      event.preventDefault();
      alert('Выберите дату');
      return;
    }

    if (start.value >= end.value) {
      event.preventDefault();
      alert('Время конца должно быть позже времени начала');
      return;
    }

    startHidden.value = `${date.value}T${start.value}:00`;
    endHidden.value = `${date.value}T${end.value}:00`;
  });

  updatePreview();
})();
