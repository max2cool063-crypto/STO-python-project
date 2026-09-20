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
      const error = document.createElement('p');
      error.id = `${input.id}-validation-error`;
      error.className = 'password-field-error';
      error.setAttribute('role', 'alert');
      error.hidden = true;
      wrapper.after(error);
      const describedBy = input.getAttribute('aria-describedby');
      const clearError = () => {
        error.hidden = true;
        error.textContent = '';
        input.removeAttribute('aria-invalid');
        if (describedBy) input.setAttribute('aria-describedby', describedBy);
        else input.removeAttribute('aria-describedby');
      };
      input.addEventListener('invalid', () => {
        error.textContent = input.validity.valueMissing ? 'Введите пароль.' :
          input.validity.tooShort ? `Пароль должен содержать не менее ${input.minLength} символов.` :
          input.validationMessage;
        error.hidden = false;
        input.setAttribute('aria-invalid', 'true');
        input.setAttribute('aria-describedby', [describedBy, error.id].filter(Boolean).join(' '));
      });
      input.addEventListener('input', clearError);
      input.form?.addEventListener('reset', clearError);
      // Also track the existing password generator revealing the generated value.
      new MutationObserver(sync).observe(input, { attributes: true, attributeFilter: ['type'] });
      input.form?.addEventListener('submit', hide);
      input.form?.addEventListener('reset', hide);
      sync();
    });
  }
  enhance();
  const serverError = document.querySelector('[data-password-error]') ||
    (controls.size ? document.querySelector('.messages .alert-error, .errornote') : null);
  if (serverError) requestAnimationFrame(() => {
    serverError.tabIndex = -1;
    serverError.focus({ preventScroll: true });
    serverError.scrollIntoView({ block: 'center', behavior: 'instant' });
  });
  new MutationObserver(enhance).observe(document.body, { childList: true, subtree: true });
  window.addEventListener('pagehide', () => controls.forEach((hide) => hide()));
})();
