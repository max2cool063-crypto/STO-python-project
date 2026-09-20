(() => {
  if (!window.isSecureContext || !('serviceWorker' in navigator)) return;
  navigator.serviceWorker.register('/service-worker.js', {scope: '/', updateViaCache: 'none'})
    .catch(() => { /* The website remains usable when workers are unavailable. */ });
  const standalone = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone;
  if (standalone()) return;
  let dismissed = false;
  try { dismissed = sessionStorage.getItem('sto-pwa-dismissed') === '1'; } catch (_) {}
  if (dismissed) return;
  let promptEvent;
  const panel = document.createElement('aside');
  panel.className = 'pwa-install';
  panel.setAttribute('aria-label', 'Установка приложения');
  panel.hidden = true;
  const text = document.createElement('p');
  text.textContent = 'ТО Онлайн на главном экране — быстрый доступ к вашим записям.';
  const actions = document.createElement('div');
  actions.className = 'pwa-install-actions';
  const install = document.createElement('button');
  install.type = 'button'; install.dataset.install = ''; install.textContent = 'Установить приложение';
  const close = document.createElement('button');
  close.type = 'button'; close.textContent = 'Позже';
  close.addEventListener('click', () => {
    dismissed = true; panel.hidden = true;
    try { sessionStorage.setItem('sto-pwa-dismissed', '1'); } catch (_) {}
  });
  install.addEventListener('click', async () => {
    if (!promptEvent) return;
    const event = promptEvent; promptEvent = null; panel.hidden = true;
    try { await event.prompt(); await event.userChoice; } catch (_) {}
  });
  actions.append(install, close); panel.append(text, actions);
  (document.querySelector('main') || document.body).append(panel);
  window.addEventListener('beforeinstallprompt', event => {
    if (dismissed || standalone()) return;
    event.preventDefault(); promptEvent = event; install.hidden = false; panel.hidden = false;
  });
  window.addEventListener('appinstalled', () => { panel.hidden = true; promptEvent = null; });
  if (/iPad|iPhone|iPod/.test(navigator.userAgent) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) {
    text.textContent = 'Чтобы добавить ТО Онлайн на главный экран, откройте меню «Поделиться» и выберите «На экран Домой». Если пункта нет, откройте сайт в Safari.';
    install.hidden = true; panel.hidden = false;
  }
})();
