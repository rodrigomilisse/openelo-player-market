// Shared shell for every page: header with search, mock-data note, waitlist footer, formatters, chart.
import { search, isMock } from './api.js';

export const number = new Intl.NumberFormat('en-GB');
export const signed = (v) => (v > 0 ? `+${number.format(v)}` : v < 0 ? `−${number.format(-v)}` : '0');
export const direction = (v) => (v > 0 ? 'up' : v < 0 ? 'down' : 'flat');
export const asDate = (iso) => new Date(`${iso}T12:00:00Z`);
export const shortDate = (iso) => asDate(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
export const longDate = (iso) => asDate(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
export const playerUrl = (id) => `player.html?id=${encodeURIComponent(id)}`;
export const clubUrl = (id) => `club.html?id=${encodeURIComponent(id)}`;
export const escape = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const field = (name, root = document) => root.querySelector(`[data-field="${name}"]`);
export const param = (name) => new URLSearchParams(location.search).get(name);

const NAV = [
  ['index.html', 'This week'], ['rankings.html', 'Rankings'], ['leagues.html', 'Leagues'],
  ['compare.html', 'Compare'], ['how.html', 'How it works'],
];

export function shell() {
  const here = location.pathname.split('/').pop() || 'index.html';
  const header = document.querySelector('[data-shell="header"]');
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
    <nav aria-label="Main">${NAV.map(([href, label]) => `<a href="${href}"${href === here ? ' aria-current="page"' : ''}>${label}</a>`).join('')}</nav>
    <div class="header-end">
      <div class="search" role="search">
        <label class="visually-hidden" for="site-search">Find a player or club</label>
        <input id="site-search" type="search" placeholder="Find a player or club" autocomplete="off">
        <ul class="search-results" aria-label="Search results"></ul>
      </div>
      <a class="header-cta" href="#waitlist">Join the waitlist</a>
    </div>`;
  if (isMock) {
    const note = document.createElement('p');
    note.className = 'mock-note';
    note.innerHTML = '<strong>Mock data.</strong> Every player, club and number here is fictional, generated to build the site.';
    header.after(note);
  }
  wireSearch(header);
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
    <footer class="site-footer"><p>OpenElo rates players from public match results and minutes played. Ratings are not a valuation, a transfer fee or an offer of anything.</p></footer>`;
  // No backend yet: the form confirms locally. Wire it to the waitlist endpoint when it exists.
  footer.querySelector('form').addEventListener('submit', (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    footer.querySelector('.waitlist-status').textContent = `You're on the list. We'll email ${form.email.value} when the market opens in ${form.country.value}.`;
    form.reset();
  });
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
