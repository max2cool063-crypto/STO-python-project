/* =========================================================
   STO Booking — Lucide icon runtime v1
   Centralized icon rendering plus compatibility migration for
   legacy public/client glyphs. Visual layer only.
   ========================================================= */
(function () {
  const legacyIconMap = {
    'discovery-action': 'map-pin',
    'hero-clock': 'clock-3',
    'hero-home': 'home',
    'station-building': 'home',
    'station-pin': 'map-pin',
    'station-clock': 'clock-3',
    'station-arrow': 'arrow-right',
    'station-empty': 'map-pin',
    'station-more': 'chevron-down',
    'booking-back': 'arrow-left',
    'booking-address': 'map-pin',
    'booking-trust': 'check',
    'booking-location': 'map-pin',
    'booking-calendar': 'calendar-days',
    'booking-car': 'car-front',
    'booking-truck': 'truck',
    'booking-camera': 'camera',
    'booking-arrow': 'arrow-right',
    'booking-building': 'bookmark',
    'booking-more': 'chevron-down',
    'auth-check': 'check',
    'auth-mail': 'mail',
    'header-chevron': 'chevron-down',
    'cabinet-calendar': 'calendar-days',
    'cabinet-car': 'car-front',
    'cabinet-empty': 'calendar-x',
    'cabinet-close': 'x'
  };

  function hasDeclaredIcon(element) {
    return !!(element && (element.querySelector('.lucide') || element.querySelector('[data-lucide]')));
  }

  function replaceLegacyIconElement(element, iconName) {
    if (!element || hasDeclaredIcon(element)) return;
    element.textContent = '';
    element.setAttribute('data-lucide', iconName);
    element.setAttribute('aria-hidden', 'true');
  }

  function replaceFirstTextWithIcon(element, iconName, glyphPattern) {
    if (!element || hasDeclaredIcon(element)) return;
    const icon = document.createElement('i');
    icon.setAttribute('data-lucide', iconName);
    icon.setAttribute('aria-hidden', 'true');
    element.insertBefore(icon, element.firstChild);
    const firstText = Array.from(element.childNodes).find(function (node) {
      return node.nodeType === Node.TEXT_NODE && node.textContent.trim();
    });
    if (firstText) {
      firstText.textContent = firstText.textContent.replace(glyphPattern || /^\s*[⌖◷✓✉→←↓↑]\s*/, ' ');
    }
  }

  function migrateLegacyGlyphs(root) {
    const scope = root || document;

    scope.querySelectorAll('.discovery-hero__actions > a > span').forEach(el => replaceLegacyIconElement(el, legacyIconMap['discovery-action']));
    scope.querySelectorAll('.hero-benefit-icon').forEach(function (el) {
      if (hasDeclaredIcon(el)) return;
      replaceLegacyIconElement(el, el.textContent.trim() === '⌂' ? legacyIconMap['hero-home'] : legacyIconMap['hero-clock']);
    });
    scope.querySelectorAll('.station-card-icon').forEach(el => replaceLegacyIconElement(el, legacyIconMap['station-building']));
    scope.querySelectorAll('.station-address').forEach(el => replaceFirstTextWithIcon(el, legacyIconMap['station-pin']));
    scope.querySelectorAll('.station-hours').forEach(el => replaceFirstTextWithIcon(el, legacyIconMap['station-clock']));
    scope.querySelectorAll('.station-card-arrow').forEach(el => replaceLegacyIconElement(el, legacyIconMap['station-arrow']));
    scope.querySelectorAll('.empty-state-icon, .station-map-empty__icon').forEach(el => replaceLegacyIconElement(el, legacyIconMap['station-empty']));
    scope.querySelectorAll('.station-show-more span').forEach(el => replaceLegacyIconElement(el, legacyIconMap['station-more']));

    scope.querySelectorAll('.booking-back a').forEach(el => replaceFirstTextWithIcon(el, legacyIconMap['booking-back']));
    scope.querySelectorAll('.booking-station-address').forEach(function (el) {
      el.querySelectorAll(':scope > span[aria-hidden="true"]').forEach(function (legacyGlyph) {
        legacyGlyph.remove();
      });
      replaceFirstTextWithIcon(el, legacyIconMap['booking-address']);
    });
    scope.querySelectorAll('.booking-trust-icon').forEach(el => replaceLegacyIconElement(el, legacyIconMap['booking-trust']));
    scope.querySelectorAll('.booking-location-icon').forEach(el => replaceLegacyIconElement(el, legacyIconMap['booking-location']));
    scope.querySelectorAll('.booking-calendar-icon').forEach(function (el) {
      replaceLegacyIconElement(el, el.textContent.trim() === '🚗' ? legacyIconMap['booking-car'] : legacyIconMap['booking-calendar']);
    });
    scope.querySelectorAll('.truck-warning > span').forEach(el => replaceLegacyIconElement(el, legacyIconMap['booking-truck']));
    scope.querySelectorAll('.booking-photo-drop > span').forEach(el => replaceLegacyIconElement(el, legacyIconMap['booking-camera']));
    scope.querySelectorAll('#submit-btn > span').forEach(el => replaceLegacyIconElement(el, legacyIconMap['booking-arrow']));
    scope.querySelectorAll('.booking-other-card__icon').forEach(el => replaceLegacyIconElement(el, legacyIconMap['booking-building']));
    scope.querySelectorAll('.booking-other-card .station-status').forEach(function (el) {
      Array.from(el.childNodes).forEach(function (node) {
        if (node.nodeType === Node.TEXT_NODE && node.textContent.includes('Активна')) {
          node.textContent = node.textContent.replace('Активна', 'Открыта');
        }
      });
    });
    scope.querySelectorAll('.booking-other-card__address').forEach(el => replaceFirstTextWithIcon(el, legacyIconMap['booking-address']));
    scope.querySelectorAll('.booking-other-card__link b').forEach(el => replaceLegacyIconElement(el, legacyIconMap['booking-arrow']));
    scope.querySelectorAll('.booking-show-more span').forEach(el => replaceLegacyIconElement(el, legacyIconMap['booking-more']));

    scope.querySelectorAll('.auth-benefit').forEach(el => replaceFirstTextWithIcon(el, legacyIconMap['auth-check'], /^\s*✓\s*/));
    scope.querySelectorAll('.auth-note > span:first-child').forEach(el => replaceLegacyIconElement(el, legacyIconMap['auth-mail']));
    scope.querySelectorAll('.auth-page .btn span[aria-hidden="true"]').forEach(el => replaceLegacyIconElement(el, legacyIconMap['booking-arrow']));
    scope.querySelectorAll('.header-user__chevron').forEach(el => replaceLegacyIconElement(el, legacyIconMap['header-chevron']));

    scope.querySelectorAll('.appt-date-modern').forEach(el => replaceFirstTextWithIcon(el, legacyIconMap['cabinet-calendar'], /^\s*📅\s*/));
    scope.querySelectorAll('.appt-car-modern').forEach(el => replaceFirstTextWithIcon(el, legacyIconMap['cabinet-car'], /^\s*🚗\s*/));
    scope.querySelectorAll('.cabinet-empty__icon').forEach(el => replaceLegacyIconElement(el, legacyIconMap['cabinet-empty']));
    scope.querySelectorAll('.cabinet-photo-lightbox__close').forEach(el => replaceLegacyIconElement(el, legacyIconMap['cabinet-close']));
  }

  function refreshIcons(root) {
    const scope = root || document;
    migrateLegacyGlyphs(scope);
    if (!window.lucide || typeof window.lucide.createIcons !== 'function') return;
    window.lucide.createIcons({
      root: scope,
      attrs: { 'aria-hidden': 'true', focusable: 'false' }
    });

    // Booking page: make the bookmark itself visually small while keeping
    // the 36px clickable/background container unchanged.
    scope.querySelectorAll('.booking-other-card__icon').forEach(function (container) {
      const icon = container.querySelector('svg');
      if (!icon) return;
      icon.style.setProperty('width', '24px', 'important');
      icon.style.setProperty('height', '24px', 'important');
      icon.style.setProperty('stroke-width', '2', 'important');
      icon.style.setProperty('flex', '0 0 auto', 'important');
      icon.style.setProperty('transform', 'scale(0.42)', 'important');
      icon.style.setProperty('transform-origin', 'center center', 'important');
    });
  }

  window.STOIcons = window.STOIcons || {};
  window.STOIcons.refresh = refreshIcons;

  document.addEventListener('DOMContentLoaded', function () {
    refreshIcons(document);
    if (window.MutationObserver) {
      const observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
          mutation.addedNodes.forEach(function (node) {
            if (node.nodeType === Node.ELEMENT_NODE) refreshIcons(node);
          });
        });
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }
  });

  document.addEventListener('sto:icons-refresh', function (event) {
    refreshIcons(event.detail && event.detail.root ? event.detail.root : document);
  });
})();
