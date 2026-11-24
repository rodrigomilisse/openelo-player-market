// Page shell: the glass refraction filter, the pointer light on glass, and the theme toggle.

// Chromium uses this SVG filter for refraction behind glass; other browsers fall back to a blur.
document.body.insertAdjacentHTML('afterbegin', `<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <filter id="liquid-refraction" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">
    <feTurbulence type="fractalNoise" baseFrequency="0.008 0.012" numOctaves="2" seed="7" result="noise"/>
    <feGaussianBlur in="noise" stdDeviation="2" result="soft"/>
    <feDisplacementMap in="SourceGraphic" in2="soft" scale="34" xChannelSelector="R" yChannelSelector="G"/>
  </filter></svg>`);

// The highlight on glass follows the pointer.
let lit = null;
document.addEventListener('pointermove', (event) => {
  const el = event.target.closest?.('.glass-panel, .liquid');
  if (lit && lit !== el) lit.style.setProperty('--lit', '0.55');
  lit = el;
  if (!el) return;
  const box = el.getBoundingClientRect();
  el.style.setProperty('--mx', `${event.clientX - box.left}px`);
  el.style.setProperty('--my', `${event.clientY - box.top}px`);
  el.style.setProperty('--lit', '1');
}, { passive: true });

// Light or dark: the system's choice until the reader picks one. The scene listens for 'themechange'.
const SUN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
const MOON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>';
const toggle = document.querySelector('[data-theme-toggle]');
function showTheme() {
  const dark = document.documentElement.dataset.theme !== 'light';
  toggle.innerHTML = dark ? SUN : MOON;
  toggle.setAttribute('aria-label', dark ? 'Switch to light theme' : 'Switch to dark theme');
}
toggle?.addEventListener('click', () => {
  const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem('site-theme', next); } catch { /* storage blocked: still switches for this visit */ }
  showTheme();
  window.dispatchEvent(new CustomEvent('themechange', { detail: next }));
});
if (toggle) showTheme();
