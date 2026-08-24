/* =========================================================
   STO Booking — Lucide icon runtime v1
   Keeps icon rendering centralized so templates only declare
   data-lucide="icon-name".
   ========================================================= */
(function () {
  function refreshIcons(root) {
    if (!window.lucide || typeof window.lucide.createIcons !== 'function') {
      return;
    }

    window.lucide.createIcons({
      root: root || document,
      attrs: {
        'aria-hidden': 'true',
        focusable: 'false'
      }
    });
  }

  window.STOIcons = window.STOIcons || {};
  window.STOIcons.refresh = refreshIcons;

  document.addEventListener('DOMContentLoaded', function () {
    refreshIcons(document);
  });

  document.addEventListener('sto:icons-refresh', function (event) {
    refreshIcons(event.detail && event.detail.root ? event.detail.root : document);
  });
})();
