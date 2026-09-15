(() => {
  const main = document.querySelector('.app-main');
  if (!main) return;
  main.querySelectorAll('.tabular table').forEach((table) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'admin-table-scroll';
    table.before(wrapper);
    wrapper.append(table);
  });
  const regions = [...main.querySelectorAll('.table-responsive, .admin-table-scroll')].map((region) => {
    const hint = document.createElement('p');
    hint.className = 'admin-scroll-hint';
    hint.textContent = 'Все столбцы доступны при прокрутке таблицы влево и вправо →';
    region.before(hint);
    region.setAttribute('role', 'region');
    region.setAttribute('aria-label', 'Таблица с горизонтальной прокруткой');
    return {region, hint};
  });
  const update = () => regions.forEach(({region, hint}) => {
    const scrollable = region.clientWidth > 0 && region.scrollWidth > region.clientWidth + 1;
    hint.classList.toggle('is-needed', scrollable);
    if (scrollable) region.tabIndex = 0;
    else region.removeAttribute('tabindex');
  });
  const observer = new ResizeObserver(update);
  regions.forEach(({region}) => observer.observe(region));
  update();
})();
