(() => {
  // Keep desktop tables intact; on phones, label every field in each card.
  document.querySelectorAll('.st-main .st-table').forEach((table) => {
    const labels = [...table.querySelectorAll('thead th')].map((th) => th.textContent.trim());
    table.querySelectorAll('tbody tr').forEach((row) => {
      [...row.cells].forEach((cell, index) => {
        if (cell.colSpan === 1 && labels[index]) cell.dataset.label = labels[index];
      });
    });
    table.classList.add('st-mobile-table');
  });
  const button = document.querySelector('.st-menu-toggle');
  const panel = document.getElementById('st-menu-panel');
  if (!button || !panel) return;
  const mobile = window.matchMedia('(max-width: 760px)');
  const state = button.querySelector('.st-menu-toggle__state');
  const setExpanded = (expanded) => {
    panel.hidden = !expanded;
    button.setAttribute('aria-expanded', String(expanded));
    state.textContent = expanded ? 'Скрыть' : 'Открыть';
  };
  const syncViewport = () => {
    button.hidden = !mobile.matches;
    setExpanded(!mobile.matches);
  };
  button.addEventListener('click', () => setExpanded(panel.hidden));
  panel.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && mobile.matches) {
      setExpanded(false);
      button.focus();
    }
  });
  mobile.addEventListener('change', syncViewport);
  syncViewport();
})();
