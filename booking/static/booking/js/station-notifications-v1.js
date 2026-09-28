(function () {
  'use strict';

  var root = document.querySelector('[data-station-notifications]');
  function appBadge(count) {
    try {
      var result = count > 0 ? navigator.setAppBadge?.(count) : navigator.clearAppBadge?.();
      Promise.resolve(result).catch(function () {});
    } catch (_) { /* Unsupported or disallowed badging must not break the bell. */ }
  }
  if (!root) { appBadge(0); return; }
  var stopped = false;
  var loading = false;

  var toggle = root.querySelector('[data-notification-toggle]');
  var panel = root.querySelector('[data-notification-panel]');
  var badge = root.querySelector('[data-notification-count]');
  var list = root.querySelector('[data-notification-list]');
  var readAll = root.querySelector('[data-notification-read-all]');
  var endpoint = root.dataset.endpoint;
  var readAllUrl = root.dataset.readAllUrl;
  var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || getCookie('csrftoken');

  function getCookie(name) {
    var value = ('; ' + document.cookie).split('; ' + name + '=');
    if (value.length === 2) return decodeURIComponent(value.pop().split(';').shift());
    return '';
  }

  function escapeHtml(value) {
    var div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  function formatTime(value) {
    var date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleString('ru-RU', {day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit'});
  }

  function updateBadge(count) {
    count = Number(count);
    count = Number.isSafeInteger(count) && count > 0 ? count : 0;
    badge.textContent = count > 99 ? '99+' : String(count);
    badge.hidden = count === 0;
    toggle.setAttribute('aria-label', count ? 'Уведомления: ' + count + ' непрочитанных' : 'Уведомления');
    appBadge(count);
  }

  function render(items) {
    if (!items.length) {
      list.innerHTML = '<div class="st-notification-empty">Нет новых уведомлений</div>';
      return;
    }
    list.innerHTML = items.map(function (item) {
      var content = '<div class="st-notification-item__title">' + escapeHtml(item.title) + '</div>' +
        '<div class="st-notification-item__message">' + escapeHtml(item.message) + '</div>' +
        '<div class="st-notification-item__time">' + escapeHtml(formatTime(item.created_at)) + '</div>';
      if (item.appointment_url) {
        return '<form method="post" action="' + escapeHtml('/station/notifications/' + item.id + '/read/') + '" class="st-notification-item-form">' +
          '<input type="hidden" name="csrfmiddlewaretoken" value="' + escapeHtml(csrfToken) + '"><button class="st-notification-item st-notification-item--unread" type="submit">' + content + '</button></form>';
      }
      return '<div class="st-notification-item st-notification-item--unread">' + content + '</div>';
    }).join('');
  }

  function load() {
    if (stopped || loading) return;
    loading = true;
    fetch(endpoint, {headers: {'X-Requested-With': 'XMLHttpRequest'}, credentials: 'same-origin', cache: 'no-store'})
      .then(function (response) {
        if (response.redirected || response.status === 401 || response.status === 403) {
          if (!stopped) updateBadge(0);
          stopped = true;
          throw new Error('notification session ended');
        }
        if (!response.ok) throw new Error('notification request failed');
        return response.json();
      })
      .then(function (data) { if (!stopped) { updateBadge(data.unread_count); render(data.notifications || []); } })
      .catch(function () {})
      .finally(function () { loading = false; });
  }

  toggle.addEventListener('click', function () {
    var open = !panel.hidden;
    panel.hidden = open;
    toggle.setAttribute('aria-expanded', String(!open));
    if (!open) load();
  });

  readAll.addEventListener('click', function () {
    fetch(readAllUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest'}
    }).then(function () { load(); });
  });

  document.addEventListener('click', function (event) {
    if (!root.contains(event.target)) {
      panel.hidden = true;
      toggle.setAttribute('aria-expanded', 'false');
    }
  });

  load();
  window.setInterval(load, 20000);
  window.addEventListener('focus', load);
  window.addEventListener('online', load);
  window.addEventListener('pageshow', function () { stopped = false; load(); });
  document.addEventListener('visibilitychange', function () { if (!document.hidden) load(); });
  document.querySelectorAll('form[action$="/logout/"]').forEach(function (form) {
    form.addEventListener('submit', function () { stopped = true; appBadge(0); });
  });
})();
