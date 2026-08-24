/* =========================================================
   STO Booking — Lucide icon runtime v1
   Centralized icon rendering plus a small compatibility layer
   for legacy public-page glyphs. The compatibility layer lets
   the UI migrate incrementally without changing behavior.
   ========================================================= */
(function () {
  const legacyIconMap = {
    'discovery-action': 'map-pin',
    'hero-clock': 'clock-3',
    'hero-home': 'shield-check',
    'station-building': 'building-2',
    'station-pin': 'map-pin',
    'station-clock': 'clock-3',
    'station-arrow': 'arrow-right',
    'station-empty': 'map-pin-off',
    'station-more': 'chevron-down'
  };

  function replaceLegacyIconElement(element, iconName) {
    if (!element || element.querySelector('.lucide')) {
      return;
    }

    element.textContent = '';
    element.setAttribute('data-lucide', iconName);
  }

  function replaceFirstTextWithIcon(element, iconName) {
    if (!element || element.querySelector('.lucide')) {
      return;
    }

    const icon = document.createElement('i');
    icon.setAttribute('data-lucide', iconName);
    icon.setAttribute('aria-hidden', 'true');
    element.insertBefore(icon, element.firstChild);

    const firstText = Array.from(element.childNodes).find(function (node) {
      return node.nodeType === Node.TEXT_NODE && node.textContent.trim();
    });
    if (firstText) {
      firstText.textContent = firstText.textContent.replace(/^\s*[⌖◷]\s*/, ' ');
    }
  }

  function migrateLegacyGlyphs(root) {
    const scope = root || document;

    scope.querySelectorAll('.discovery-hero__actions > a > span').forEach(function (element) {
      replaceLegacyIconElement(element, legacyIconMap['discovery-action']);
    });

    scope.querySelectorAll('.hero-benefit-icon').forEach(function (element) {
      const glyph = element.textContent.trim();
      replaceLegacyIconElement(
        element,
        glyph === '⌂' ? legacyIconMap['hero-home'] : legacyIconMap['hero-clock']
      );
    });

    scope.querySelectorAll('.station-card-icon').forEach(function (element) {
      replaceLegacyIconElement(element, legacyIconMap['station-building']);
    });

    scope.querySelectorAll('.station-address').forEach(function (element) {
      replaceFirstTextWithIcon(element, legacyIconMap['station-pin']);
    });

    scope.querySelectorAll('.station-hours').forEach(function (element) {
      replaceFirstTextWithIcon(element, legacyIconMap['station-clock']);
    });

    scope.querySelectorAll('.station-card-arrow').forEach(function (element) {
      replaceLegacyIconElement(element, legacyIconMap['station-arrow']);
    });

    scope.querySelectorAll('.empty-state-icon, .station-map-empty__icon').forEach(function (element) {
      replaceLegacyIconElement(element, legacyIconMap['station-empty']);
    });

    scope.querySelectorAll('.station-show-more span').forEach(function (element) {
      replaceLegacyIconElement(element, legacyIconMap['station-more']);
    });
  }

  function refreshIcons(root) {
    const scope = root || document;
    migrateLegacyGlyphs(scope);

    if (!window.lucide || typeof window.lucide.createIcons !== 'function') {
      return;
    }

    window.lucide.createIcons({
      root: scope,
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
