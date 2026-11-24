// Shared shell for every page: header with search, mock-data note, waitlist footer, formatters, chart.
import { search, isMock } from './api.js';
import { install } from './router.js';
import { CONFIG } from './config.js';

export const number = new Intl.NumberFormat('en-GB');
export const signed = (v) => (v > 0 ? `+${number.format(v)}` : v < 0 ? `−${number.format(-v)}` : '0');
export const direction = (v) => (v > 0 ? 'up' : v < 0 ? 'down' : 'flat');
export const asDate = (iso) => new Date(`${iso}T12:00:00Z`);
export const shortDate = (iso) => asDate(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
export const longDate = (iso) => asDate(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
// The build writes a page per player and club (player-<id>.html) and sets CONFIG.staticPages; otherwise the query form.
export const playerUrl = (id) => (CONFIG.staticPages ? `player-${encodeURIComponent(id)}.html` : `player.html?id=${encodeURIComponent(id)}`);
export const clubUrl = (id) => (CONFIG.staticPages ? `club-${encodeURIComponent(id)}.html` : `club.html?id=${encodeURIComponent(id)}`);
export const escape = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const field = (name, root = document) => root.querySelector(`[data-field="${name}"]`);
export const param = (name) => new URLSearchParams(location.search).get(name);

// Two modes on one site: Explore (the ratings, loud) and Market (your money, quiet). Each has its own nav.
const NAV = [
  ['index.html', 'This week'], ['rankings.html', 'Rankings'], ['leagues.html', 'Leagues'],
  ['compare.html', 'Compare'], ['how.html', 'How it works'],
];
const MARKET_NAV = [
  ['portfolio.html', 'Portfolio'], ['market.html', 'Browse'], ['dividends.html', 'Dividends'],
  ['watchlist.html', 'Watchlist'], ['activity.html', 'Activity'],
];

export function shell() {
  install();
  if (isMock) keepOutOfSearch();
  const header = document.querySelector('[data-shell="header"]');
  if (header.dataset.ready) return;   // a page change without reload: the header and footer stay
  header.dataset.ready = '1';
  const here = location.pathname.split('/').pop() || 'index.html';
  header.className = 'site-header liquid';
  document.body.insertAdjacentHTML('afterbegin', `<svg width="0" height="0" style="position:absolute" aria-hidden="true">
    <filter id="liquid-refraction" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">
      <feTurbulence type="fractalNoise" baseFrequency="0.008 0.012" numOctaves="2" seed="7" result="noise"/>
      <feGaussianBlur in="noise" stdDeviation="2" result="soft"/>
      <feDisplacementMap in="SourceGraphic" in2="soft" scale="34" xChannelSelector="R" yChannelSelector="G"/>
    </filter></svg>`);
  wireLight();
  header.innerHTML = `
    <a class="logo" href="index.html">OpenElo</a>
    <div class="mode-switch" role="group" aria-label="Mode"><a href="index.html" data-mode="explore">Explore</a><a href="portfolio.html" data-mode="market">Market</a></div>
    <nav aria-label="Main" class="nav-explore">${NAV.map(([href, label]) => `<a href="${href}"${href === here ? ' aria-current="page"' : ''}>${label}</a>`).join('')}</nav>
    <nav aria-label="Market" class="nav-market">${MARKET_NAV.map(([href, label]) => `<a href="${href}"${href === here ? ' aria-current="page"' : ''}>${label}</a>`).join('')}</nav>
    <div class="header-end">
      <button class="theme-toggle" type="button" data-theme-toggle></button>
      <div class="search" role="search">
        <label class="visually-hidden" for="site-search">Find a player or club</label>
        <input id="site-search" type="search" placeholder="Find a player or club" autocomplete="off">
        <ul class="search-results" aria-label="Search results"></ul>
      </div>
      <a class="header-cta" href="#waitlist">Join the waitlist</a>
      <button class="m-search-btn" type="button" data-mobile-only aria-label="Search" aria-expanded="false">${ICON.search}</button>
    </div>`;
  const note = document.createElement('p');
  note.className = 'mock-note';
  note.innerHTML = isMock ? '<strong>Mock data.</strong> <span>Every player, club and number here is fictional, generated to build the site.</span>'
    : '<strong>Beta.</strong> <span>Real ratings from real results, still provisional while the formula is tested. Market prices are simulated.</span>';
  header.after(note);
  wireSearch(header);
  wireTheme(header);
  buildTabs(here);
  wireMobile(header, note);
  const footer = document.querySelector('[data-shell="footer"]');
  footer.innerHTML = `
    <section id="waitlist" class="waitlist" aria-labelledby="waitlist-title">
      <h2 id="waitlist-title">Back players' ratings when the market opens</h2>
      <p>The OpenElo market will let you hold shares in players and earn as their rating climbs. Join the waitlist to hear when it opens in your country.</p>
      <form class="waitlist-form">
        <label class="visually-hidden" for="waitlist-email">Email address</label>
        <input id="waitlist-email" name="email" type="email" required autocomplete="email" placeholder="you@example.com">
        <label class="visually-hidden" for="waitlist-country">Country</label>
        <input id="waitlist-country" name="country" required autocomplete="country-name" placeholder="Your country">
        <button type="submit">Join the waitlist</button>
      </form>
      <p class="waitlist-status" role="status"></p>
    </section>
    <footer class="site-footer"><p>OpenElo rates players from public match results and minutes played. Ratings are not a valuation, a transfer fee or an offer of anything.</p>
      <nav class="footer-links" aria-label="About OpenElo"><a href="about.html">About</a><a href="how.html">How it works</a><a href="privacy.html">Privacy</a><a href="terms.html">Terms</a></nav></footer>`;
  // The waitlist posts to CONFIG.waitlistUrl when it is set; without it the form only confirms locally.
  footer.querySelector('form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget, status = footer.querySelector('.waitlist-status');
    const entry = { email: form.email.value, country: form.country.value, page: location.pathname };
    if (CONFIG.waitlistUrl) {
      status.textContent = 'Adding you…';
      try {
        const r = await fetch(CONFIG.waitlistUrl, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(entry) });
        if (!r.ok) throw new Error(String(r.status));
      } catch {
        status.textContent = "That didn't go through. Please try again in a moment.";
        return;
      }
    }
    track('waitlist', { country: entry.country });
    status.textContent = `You're on the list. We'll email ${entry.email} when the market opens in ${entry.country}.`;
    form.reset();
  });
  const contact = () => { if (CONFIG.contactEmail) document.querySelectorAll('a[href^="mailto:hello@openelo.example"]').forEach((a) => { a.href = `mailto:${CONFIG.contactEmail}`; a.textContent = CONFIG.contactEmail; }); };
  contact();
  window.addEventListener('openelo:navigate', contact);
  loadAnalytics();
}

/* Analytics: off unless CONFIG.analytics names a provider. Page changes without reload are counted too. */
let analyticsOn = false;
function loadAnalytics() {
  const domain = CONFIG.analytics?.plausibleDomain;
  if (!domain || analyticsOn) return;
  analyticsOn = true;
  window.plausible = window.plausible || function () { (window.plausible.q = window.plausible.q || []).push(arguments); };
  document.head.append(Object.assign(document.createElement('script'), { defer: true, src: 'https://plausible.io/js/script.manual.js', dataset: { domain } }));
  window.plausible('pageview');
  window.addEventListener('openelo:navigate', () => window.plausible('pageview'));
}
export function track(event, props) { if (analyticsOn) window.plausible(event, { props }); }

/* Light or dark: the system's choice until the reader picks one; the scene listens for 'themechange'. */
const SUN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6"/></svg>';
const MOON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z"/></svg>';
export const theme = () => (document.documentElement.dataset.theme === 'light' ? 'light' : 'dark');
function wireTheme(header) {
  const btn = header.querySelector('[data-theme-toggle]');
  const show = () => { const light = theme() === 'light'; btn.innerHTML = light ? MOON : SUN; btn.setAttribute('aria-label', light ? 'Switch to dark mode' : 'Switch to light mode'); };
  const set = (t, save) => {
    document.documentElement.dataset.theme = t;
    if (save) { try { localStorage.setItem('openelo-theme', t); } catch { /* storage blocked */ } }
    show(); window.dispatchEvent(new CustomEvent('themechange', { detail: t }));
  };
  btn.addEventListener('click', () => set(theme() === 'light' ? 'dark' : 'light', true));
  matchMedia('(prefers-color-scheme: light)').addEventListener('change', (e) => {
    let saved = null; try { saved = localStorage.getItem('openelo-theme'); } catch { /* */ }
    if (!saved) set(e.matches ? 'light' : 'dark', false);
  });
  show();
}

/* Liquid glass catches the light where the pointer is. */
function wireLight() {
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
}

function wireSearch(header) {
  const input = header.querySelector('#site-search');
  const list = header.querySelector('.search-results');
  let token = 0;
  input.addEventListener('input', async () => {
    const mine = ++token;
    const results = input.value.trim().length < 2 ? [] : await search(input.value);
    if (mine !== token) return;
    list.innerHTML = results.map((r) => `<li><a href="${r.kind === 'club' ? clubUrl(r.id) : playerUrl(r.id)}">${escape(r.name)}<small>${r.kind === 'club' ? 'Club, ' : ''}${escape(r.detail)}</small><span class="r">${number.format(r.rating)}</span></a></li>`).join('');
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') { const first = list.querySelector('a'); if (first) location.href = first.href; }
    if (event.key === 'Escape') { input.value = ''; list.innerHTML = ''; }
  });
  document.addEventListener('click', (event) => { if (!header.querySelector('.search').contains(event.target)) list.innerHTML = ''; });
}

export function notFound(what) {
  document.querySelector('main').innerHTML = `<section class="page-head"><h1>Not found</h1><p class="lede">No ${what} has this address. Check the link, or find them in the <a href="rankings.html">rankings</a>.</p></section>`;
}

/* A line chart over dates. series: [{ label, cls, values, color }]; band: [i, j] shades between two series.
   read(i) returns the readout HTML for a pointed date. Redraws on resize. */
export function lineChart(svg, readout, { dates, series, band, moments = [], format = number.format, read, idle, pad: padIn }) {
  const all = series.flatMap((s) => s.values.filter((v) => v != null));
  const span = Math.max(...all) - Math.min(...all) || 1;
  const lo = Math.min(...all) - span * 0.08;
  const hi = Math.max(...all) + span * 0.08;
  readout.innerHTML = idle || '';
  function draw() {
    const width = svg.clientWidth;
    const height = svg.clientHeight;
    const pad = { l: 46, r: 12, t: moments.length ? 26 : 12, b: 26, ...padIn };
    const x = (i) => pad.l + (i / Math.max(1, dates.length - 1)) * (width - pad.l - pad.r);
    const y = (v) => pad.t + (1 - (v - lo) / (hi - lo)) * (height - pad.t - pad.b);
    const path = (values) => values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('');
    const ticks = niceTicks(lo, hi, 4);
    const months = dates.map((d, i) => [i, asDate(d)]).filter(([, d], k, list) => k === 0 || d.getUTCMonth() !== list[k - 1][1].getUTCMonth());
    let bandPath = '';
    if (band) {
      const [a, b] = band.map((k) => series[k].values);
      bandPath = `${path(a)}${b.map((_, i) => `L${x(b.length - 1 - i).toFixed(1)},${y(b[b.length - 1 - i]).toFixed(1)}`).join('')}Z`;
    }
    const pinned = moments.map((m) => [dates.indexOf(m.date), m]).filter(([i]) => i >= 0);
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.innerHTML = `
      <defs><linearGradient id="bandFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFD66B" stop-opacity="0.22"/><stop offset="1" stop-color="#FFD66B" stop-opacity="0.04"/></linearGradient></defs>
      <g class="grid">${ticks.map((v) => `<line x1="${pad.l}" x2="${width - pad.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${pad.l - 8}" y="${y(v) + 4}" text-anchor="end">${format(v)}</text>`).join('')}</g>
      <g class="axis">${months.map(([i, d]) => `<text x="${x(i)}" y="${height - 6}" text-anchor="${i === 0 ? 'start' : 'middle'}">${d.toLocaleString('en-GB', { month: 'short', timeZone: 'UTC' })}</text>`).join('')}</g>
      ${band ? `<path class="band" d="${bandPath}"/>` : ''}
      ${series.map((s) => `<path class="line ${s.cls}" d="${path(s.values)}"/>`).join('')}
      ${pinned.map(([i, m]) => `<g class="moment"><line x1="${x(i)}" x2="${x(i)}" y1="${pad.t - 6}" y2="${height - pad.b}"/>
        <circle cx="${x(i)}" cy="${y(series[0].values[i])}" r="4.5"/>
        <text x="${x(i) + (i > dates.length * 0.7 ? -8 : 8)}" y="${pad.t - 10}" text-anchor="${i > dates.length * 0.7 ? 'end' : 'start'}">${escape(m.text)}</text></g>`).join('')}
      <g class="cursor" visibility="hidden"><line y1="${pad.t}" y2="${height - pad.b}"/>${series.map((s) => `<circle r="4.5" fill="${s.color}"/>`).join('')}</g>`;
    const cursor = svg.querySelector('.cursor');
    const show = (i) => {
      cursor.setAttribute('visibility', 'visible');
      const line = cursor.querySelector('line');
      line.setAttribute('x1', x(i)); line.setAttribute('x2', x(i));
      cursor.querySelectorAll('circle').forEach((c, k) => { c.setAttribute('cx', x(i)); c.setAttribute('cy', y(series[k].values[i])); });
      if (read) readout.innerHTML = read(i);
    };
    const pick = (event) => {
      const box = svg.getBoundingClientRect();
      const i = Math.round(((event.clientX - box.left - pad.l) / (box.width - pad.l - pad.r)) * (dates.length - 1));
      show(Math.max(0, Math.min(dates.length - 1, i)));
    };
    svg.onpointermove = pick;
    svg.onpointerdown = pick;
    svg.onpointerleave = () => { cursor.setAttribute('visibility', 'hidden'); readout.innerHTML = idle || ''; };
  }
  draw();
  new ResizeObserver(draw).observe(svg);
}

function niceTicks(lo, hi, count) {
  const raw = (hi - lo) / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) || raw;
  const ticks = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) ticks.push(Math.round(v * 100) / 100);
  return ticks;
}

export function moverRow(r, { showClub = true } = {}) {
  return `<li class="mover"><a href="${playerUrl(r.id)}">${escape(r.name)}</a>
    <small>${showClub ? `${escape(r.club)}. ` : ''}${escape(r.note || '')}</small>
    <span class="e">${number.format(r.rating)}</span><span class="c ${direction(r.change)}">${signed(r.change)}</span></li>`;
}

/* Mock data must never be indexed. Every committed page already says noindex; this repeats it at run time for the case
   where something removed the tag, and drops any canonical link. See frontend/web/build/README.md. */
function keepOutOfSearch() {
  let tag = document.querySelector('meta[name="robots"]');
  if (!tag) { tag = document.createElement('meta'); tag.name = 'robots'; document.head.append(tag); }
  tag.content = 'noindex, nofollow';
  document.querySelector('link[rel="canonical"]')?.remove();
}

/* ---------- phones: bottom tabs, a More sheet, search that opens on tap, a header that gets out of the way ----------
   Everything here is hidden by default (data-mobile-only) and shown by mobile.css, which only loads on phones. */
const ico = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const ICON = {
  search: ico('<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>'),
  week: ico('<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>'), rankings: ico('<path d="M5 20V10M12 20V4M19 20v-7"/>'),
  leagues: ico('<path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H4v1a4 4 0 0 0 4 4M16 6h4v1a4 4 0 0 1-4 4M12 13v4M8 20h8"/>'), compare: ico('<path d="M7 4 3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7"/>'),
  more: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="5" cy="12" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="19" cy="12" r="1.7"/></svg>',
  portfolio: ico('<path d="M12 3v9h9a9 9 0 1 1-9-9zM15 3.5A9 9 0 0 1 20.5 9H15z"/>'), browse: ico('<path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z"/>'),
  dividends: ico('<circle cx="12" cy="12" r="8.5"/><path d="M12 7v10M9.5 9.7c0-1 1-1.7 2.5-1.7s2.5.7 2.5 1.7-1 1.4-2.5 1.7-2.5.7-2.5 1.8 1 1.7 2.5 1.7 2.5-.7 2.5-1.7"/>'),
  watchlist: ico('<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>'),
};
const TABS_EXPLORE = [['index.html', 'This week', 'week'], ['rankings.html', 'Rankings', 'rankings'], ['leagues.html', 'Leagues', 'leagues'], ['compare.html', 'Compare', 'compare']];
const TABS_MARKET = [['portfolio.html', 'Portfolio', 'portfolio'], ['market.html', 'Browse', 'browse'], ['dividends.html', 'Dividends', 'dividends'], ['watchlist.html', 'Watchlist', 'watchlist']];
const MORE_LINKS = [['how.html', 'How it works'], ['about.html', 'About'], ['activity.html', 'Market activity'], ['privacy.html', 'Privacy'], ['terms.html', 'Terms']];

function buildTabs(here) {
  const tabs = (list) => list.map(([href, label, icon]) => `<a href="${href}"${href === here ? ' aria-current="page"' : ''}>${ICON[icon]}<span>${label}</span></a>`).join('');
  document.body.insertAdjacentHTML('beforeend', `
    <div class="more-sheet liquid" data-mobile-only data-more-sheet hidden>
      <ul>${MORE_LINKS.map(([href, label]) => `<li><a href="${href}">${label}</a></li>`).join('')}</ul>
      <div class="more-actions"><button type="button" class="button" data-sheet-theme></button><a class="button button-gold" href="#waitlist" data-sheet-waitlist>Join the waitlist</a></div>
    </div>
    <nav class="tabbar liquid" data-mobile-only aria-label="Pages">
      <div class="tabs-explore">${tabs(TABS_EXPLORE)}<button type="button" data-more aria-expanded="false">${ICON.more}<span>More</span></button></div>
      <div class="tabs-market">${tabs(TABS_MARKET)}<button type="button" data-more aria-expanded="false">${ICON.more}<span>More</span></button></div>
    </nav>`);
}

function wireMobile(header, note) {
  const phone = matchMedia('(max-width: 860px), (max-height: 500px)');
  const searchBtn = header.querySelector('.m-search-btn'), input = header.querySelector('#site-search');
  searchBtn.addEventListener('click', () => {
    const open = header.classList.toggle('search-open');
    searchBtn.setAttribute('aria-expanded', String(open));
    if (open) input.focus(); else { input.value = ''; header.querySelector('.search-results').innerHTML = ''; }
  });
  note.addEventListener('click', () => note.classList.toggle('open'));

  // the header leaves when you scroll down and returns when you scroll up
  let last = window.scrollY;
  window.addEventListener('scroll', () => {
    const y = window.scrollY;
    if (!phone.matches || header.classList.contains('search-open')) { header.classList.remove('is-hidden'); last = y; return; }
    if (y > last + 8 && y > 140) header.classList.add('is-hidden');
    else if (y < last - 8 || y < 60) header.classList.remove('is-hidden');
    last = y;
  }, { passive: true });

  const sheet = document.querySelector('[data-more-sheet]'), moreBtns = [...document.querySelectorAll('[data-more]')];
  const themeBtn = sheet.querySelector('[data-sheet-theme]');
  const label = () => { themeBtn.textContent = theme() === 'light' ? 'Dark mode' : 'Light mode'; };
  const setSheet = (open) => { sheet.hidden = !open; moreBtns.forEach((b) => b.setAttribute('aria-expanded', String(open))); if (open) label(); };
  moreBtns.forEach((b) => b.addEventListener('click', (e) => { e.stopPropagation(); setSheet(sheet.hidden); }));
  // a click that does not bubble: the outside-tap handler below must not read it as a tap elsewhere
  themeBtn.addEventListener('click', () => { header.querySelector('[data-theme-toggle]').dispatchEvent(new MouseEvent('click')); label(); });
  sheet.addEventListener('click', (e) => { if (e.target.closest('a')) setSheet(false); });
  document.addEventListener('click', (e) => { if (!sheet.hidden && !sheet.contains(e.target)) setSheet(false); });
  window.addEventListener('openelo:navigate', () => { setSheet(false); header.classList.remove('is-hidden', 'search-open'); });
}
