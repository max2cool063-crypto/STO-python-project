(function () {
  'use strict';

  function byId(id) {
    return document.getElementById(id);
  }

  function setText(id, value) {
    var node = byId(id);
    if (node) node.textContent = value || '';
  }

  function getStationId() {
    if (typeof STATION_ID !== 'undefined') return String(STATION_ID);
    var match = window.location.pathname.match(/\/station\/(\d+)/);
    return match ? match[1] : '';
  }

  function clearNewCarFields() {
    ['new-email', 'vin-input'].forEach(function (id) {
      var node = byId(id);
      if (node) node.value = '';
    });
    var brand = byId('brand-select');
    var model = byId('model-select');
    if (brand) brand.value = '';
    if (model) model.innerHTML = '<option value="">Сначала выберите марку</option>';
  }

  function clearClientFields() {
    var name = byId('client-name');
    var phone = byId('client-phone');
    var hidden = byId('car-id-input');
    if (name) name.value = '';
    if (phone) phone.value = '';
    if (hidden) hidden.value = '';
    setText('summary-client', 'Не указан');
    setText('summary-car', 'Не выбран');
    if (typeof currentCarId !== 'undefined') currentCarId = null;
  }

  function resetDurationSummary() {
    var summary = byId('summary-type');
    if (summary) {
      summary.innerHTML = '<span>⏱</span><strong>Продолжительность определится по автомобилю</strong>';
    }
  }

  function hideNewCar() {
    var block = byId('new-car-block');
    if (block) block.hidden = true;
  }

  function showNewCar(existingPlate) {
    var block = byId('new-car-block');
    if (!block) return;

    block.hidden = false;
    var title = block.querySelector('h3');
    var description = block.querySelector('p');
    if (title) title.textContent = existingPlate ? 'Добавить новый автомобиль' : 'Автомобиль не найден';
    if (description) {
      description.textContent = existingPlate
        ? 'Госномер уже есть в базе, но можно зарегистрировать ещё один автомобиль с этим номером.'
        : 'Зарегистрируйте автомобиль прямо во время оформления записи.';
    }
  }

  function prepareNewCar() {
    clearClientFields();
    clearNewCarFields();
    resetDurationSummary();
    showNewCar(true);

    var block = byId('new-car-block');
    if (block) block.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function newCarButtonHtml() {
    return '<button type="button" class="st-btn st-btn--secondary station-add-new-car" style="justify-content:center;margin-top:10px;width:100%">＋ Добавить новый автомобиль с этим госномером</button>';
  }

  function setSelectedCar(car) {
    var hidden = byId('car-id-input');
    if (hidden) hidden.value = String(car.id);

    if (typeof currentCarId !== 'undefined') currentCarId = car.id;

    var name = byId('client-name');
    var phone = byId('client-phone');
    var ownerName = car.owner_name || '';
    if (name) name.value = ownerName;
    if (phone) phone.value = car.owner_phone || '');

    var plateInput = byId('plate-input');
    var plate = car.plate || (plateInput ? plateInput.value.trim().toUpperCase() : '');
    setText('summary-car', (car.brand || '') + ' ' + (car.model || '') + ' · ' + plate);
    setText('summary-client', ownerName || 'Не указан');

    if (typeof updateClientSummary === 'function') updateClientSummary();
    if (typeof updateDurationSummary === 'function') updateDurationSummary(car.vehicle_type);

    var dateInput = byId('date-input');
    if (dateInput && dateInput.value) {
      dateInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  function renderSingle(car) {
    var info = byId('car-info');
    if (!info) return;
    info.style.color = '#15803d';
    info.innerHTML = '<strong>Автомобиль найден:</strong> ' + escapeHtml(car.brand + ' ' + car.model) + ' · ' + escapeHtml(car.owner_name || 'Владелец не указан') + newCarButtonHtml();
    hideNewCar();
    setSelectedCar(car);
  }

  function renderAmbiguous(matches) {
    var info = byId('car-info');
    if (!info) return;

    info.style.color = '#92400e';
    var html = '<div style="padding:12px;border:1px solid #fbbf24;background:#fffbeb;border-radius:12px">' +
      '<strong>Найдено несколько автомобилей с этим госномером.</strong>' +
      '<div style="margin-top:4px;font-size:12px">Номер мог перейти на другой автомобиль или собственника. Выберите нужную запись — автоматически выбирать первую нельзя.</div>' +
      '<div style="display:grid;gap:8px;margin-top:10px">';

    matches.forEach(function (car) {
      var title = (car.brand || '') + ' ' + (car.model || '');
      var owner = car.owner_name || 'Владелец не указан';
      var details = [owner, car.owner_phone || '', car.owner_email || '', car.vin ? 'VIN: ' + car.vin : ''].filter(Boolean).join(' · ');
      html += '<button type="button" class="st-btn st-btn--secondary station-plate-match" data-car-id="' + String(car.id) + '" style="justify-content:flex-start;text-align:left;padding:10px 12px">' +
        '<span><strong>' + escapeHtml(title) + '</strong><small style="display:block;color:#64748b;margin-top:3px">' + escapeHtml(details) + '</small></span>' +
        '</button>';
    });
    html += newCarButtonHtml() + '</div></div>';
    info.innerHTML = html;
    hideNewCar();

    info.querySelectorAll('.station-plate-match').forEach(function (button) {
      button.addEventListener('click', function () {
        var id = String(button.getAttribute('data-car-id'));
        var selected = matches.find(function (car) { return String(car.id) === id; });
        if (selected) renderSingle(selected);
      });
    });
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  async function lookup() {
    var input = byId('plate-input');
    var info = byId('car-info');
    if (!input || !info) return;

    var plate = input.value.trim().toUpperCase();
    if (!plate) {
      clearClientFields();
      clearNewCarFields();
      info.textContent = 'Введите госномер.';
      info.style.color = '#b91c1c';
      showNewCar(false);
      return;
    }

    clearClientFields();
    clearNewCarFields();
    hideNewCar();
    info.style.color = '#64748b';
    info.textContent = 'Ищем автомобиль…';

    try {
      var stationId = getStationId();
      if (!stationId) throw new Error('Не удалось определить станцию');
      var response = await fetch('/api/car-by-plate/?plate=' + encodeURIComponent(plate) + '&station_id=' + encodeURIComponent(stationId),
        { headers: { 'X-Requested-With': 'XMLHttpRequest' } });

      var data = await response.json();
      if (response.status === 404 || data.error === 'not found') {
        info.style.color = '#92400e';
        info.textContent = 'Автомобиль с таким госномером не найден. Можно зарегистрировать новый.';
        showNewCar(false);
        return;
      }
      if (!response.ok) throw new Error(data.error || 'Ошибка поиска');

      if (!Array.isArray(data.matches)) {
        throw new Error('Некорректный ответ поиска: отсутствует matches');
      }

      if (data.matches.length === 1 && !data.ambiguous) {
        renderSingle(data.matches[0]);
        return;
      }

      if (data.matches.length > 1 && data.ambiguous) {
        renderAmbiguous(data.matches);
        return;
      }

      throw new Error('Некорректный ответ поиска');
    } catch (error) {
      console.error(error);
      clearClientFields();
      hideNewCar();
      info.style.color = '#b91c1c';
      info.textContent = 'Не удалось выполнить поиск автомобиля. Попробуйте ещё раз.';
    }
  }

  document.addEventListener('click', function (event) {
    var button = event.target.closest ? event.target.closest('#lookup-btn') : null;
    if (button) {
      event.preventDefault();
      event.stopImmediatePropagation();
      lookup();
      return;
    }

    var addNewCarButton = event.target.closest ? event.target.closest('.station-add-new-car') : null;
    if (addNewCarButton) {
      event.preventDefault();
      event.stopPropagation();
      prepareNewCar();
    }
  }, true);
})();
