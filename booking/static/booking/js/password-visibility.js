(() => {
  let sequence = 0;
  const controls = new Map();
  function enhance() {
    document.querySelectorAll('input[type="password"]').forEach((input) => {
      if (controls.has(input)) return;
      if (!input.id) {
        do { input.id = `password-field-${++sequence}`; } while (document.querySelectorAll(`#${input.id}`).length > 1);
        const label = input.previousElementSibling;
        if (label?.tagName === 'LABEL' && !label.htmlFor) label.htmlFor = input.id;
      }
      const wrapper = document.createElement('div');
      wrapper.className = 'password-control';
      input.before(wrapper);
      wrapper.append(input);
      input.classList.add('password-control__input');
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'password-visibility-button';
      button.setAttribute('aria-controls', input.id);
      const sync = () => {
        const visible = input.type === 'text';
        button.textContent = visible ? 'Скрыть' : 'Показать';
        button.setAttribute('aria-label', visible ? 'Скрыть пароль' : 'Показать пароль');
        button.title = visible ? 'Скрыть пароль' : 'Показать пароль';
        button.setAttribute('aria-pressed', String(visible));
      };
      const hide = () => { input.type = 'password'; sync(); };
      controls.set(input, hide);
      button.addEventListener('click', () => {
        input.type = input.type === 'password' ? 'text' : 'password';
        sync();
      });
      wrapper.append(button);
      // Also track the existing password generator revealing the generated value.
      new MutationObserver(sync).observe(input, { attributes: true, attributeFilter: ['type'] });
      input.form?.addEventListener('submit', hide);
      input.form?.addEventListener('reset', hide);
      sync();
    });
  }
  enhance();
  new MutationObserver(enhance).observe(document.body, { childList: true, subtree: true });
  window.addEventListener('pagehide', () => controls.forEach((hide) => hide()));
})();
