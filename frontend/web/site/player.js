// Player page: the rating as an equation, his season against his club's, what a move would do.
import { immersive, curveFormation, textFormation, fieldFormation } from './scene.js';
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
import { getPlayer, getClubs } from './api.js';
import { shell, field, param, number, signed, direction, shortDate, longDate, escape, clubUrl, playerUrl, lineChart, notFound } from './site.js';

shell();
const player = await getPlayer((param('id') || 'tiago-mendonca').replace(/[^a-z0-9-]/g, ''));
if (!player) {
  document.querySelector('.nameplate')?.remove();
  document.body.classList.remove('player-page');
  notFound('player');
} else {
  render(player);
  buildScene(player);
}

function render(p) {
  document.title = `${p.name}: ${number.format(p.rating)} OpenElo`;
  field('surname').textContent = p.shortName;
  fitSurname();
  field('identity').innerHTML = [`<a href="${clubUrl(p.club.id)}">${escape(p.club.name)}</a>`, p.position.toLowerCase(), p.age, p.nation && escape(p.nation)].filter(Boolean).join(', ');
  field('name').textContent = p.name;
  field('legend-player').textContent = p.shortName;
  field('legend-club').textContent = p.club.name;
  field('compare-link').href = `compare.html?a=${p.id}`;
  field('trade-link').href = `trade.html?id=${p.id}`;
  field('formula').textContent = `Rated with ${p.formula}, as of ${longDate(p.asOf)}.`;
  renderEquation(p);
  field('stage-rating').innerHTML = `<span class="gold">${number.format(p.rating)}</span>: ${escape(p.club.name)}'s ${number.format(p.club.rating)}, plus <strong>${signed(p.rating - p.club.rating)}</strong> he adds himself.`;
  renderRanks(p);
  renderSeason(p);
  renderTransfer(p);
  renderPrice(p);
  renderMatches(p, 10);
  renderHow(p);
  renderNeighbours(p);
  wireShare(p);
}

/* The surname fills the nameplate's height (desktop), and the plate's width follows the name:
   a short surname gets a wider plate and bigger letters, a long one a narrower plate. */
function fitSurname() {
  const el = field('surname');
  const fit = () => {
    if (!el.isConnected) return;   // the page is kept alive while another one shows
    el.style.fontSize = '';
    document.body.style.removeProperty('--plate');
    if (window.innerWidth <= 860) return;
    el.style.fontSize = '100px';
    const per100 = el.offsetHeight;   // vertical text: its length is its height
    if (!per100) return;
    let font = 100 * (window.innerHeight * 0.94) / per100;
    const plate = Math.min(Math.max(132, font / 0.92), window.innerWidth * 0.26);
    font = Math.min(font, plate * 0.92);
    el.style.fontSize = `${font}px`;
    document.body.style.setProperty('--plate', `${Math.round(plate)}px`);
  };
  document.fonts.ready.then(fit);
  window.addEventListener('resize', fit);
  document.querySelector('main').addEventListener('pageshow-again', fit);
}

function partValue(part, i) { return i === 0 ? number.format(part.value) : signed(part.value); }

/* The equation: club + what he adds = OpenElo. Each part explains itself. */
function renderEquation(p) {
  const list = field('parts');
  const explain = field('explain');
  const idle = `Tap a number to see where it comes from. Together they make <strong>${number.format(p.rating)}</strong>.`;
  explain.innerHTML = idle;
  list.replaceChildren(...p.parts.map((part, i) => {
    const li = document.createElement('li');
    li.className = 'part';
    li.dataset.key = part.key;
    li.dataset.sign = part.value < 0 ? 'minus' : 'plus';
    if (part.value === 0) li.dataset.zero = '';
    li.style.setProperty('--i', i);
    li.innerHTML = `<button type="button" aria-pressed="false"><span class="part-value" data-to="${part.value}" data-first="${i === 0}">${partValue(part, i)}</span>`
      + `<span class="part-label">${escape(part.label)}</span></button>`;
    li.querySelector('button').addEventListener('click', (event) => {
      const button = event.currentTarget;
      const pressed = button.getAttribute('aria-pressed') === 'true';
      list.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', 'false'));
      button.setAttribute('aria-pressed', String(!pressed));
      explain.innerHTML = pressed ? idle : `<strong>${escape(part.label)}, ${partValue(part, i)}.</strong> ${escape(part.explain)}`;
    });
    return li;
  }));
  document.querySelector('.total').style.setProperty('--i', p.parts.length);
  const total = field('rating');
  total.textContent = number.format(p.rating);
  const equation = document.querySelector('.equation');
  if (reducedMotion) { equation.classList.add('is-in'); return; }
  // One orchestrated moment: the parts count up in turn, then the total lands.
  requestAnimationFrame(() => equation.classList.add('is-in'));
  const values = [...list.querySelectorAll('.part-value')];
  values.forEach((el, i) => countUp(el, +el.dataset.to, 140 * i, 700, el.dataset.first === 'true' ? number.format : signed));
  countUp(total, p.rating, 140 * values.length + 120, 900, number.format);
}

function countUp(el, to, delay, duration, format) {
  const from = Math.abs(to) > 500 ? Math.round(to * 0.92) : 0;
  el.textContent = format(from);
  setTimeout(() => {
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      el.textContent = format(Math.round(from + (to - from) * (1 - Math.pow(1 - t, 3))));
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, delay);
}

function renderRanks(p) {
  const rows = [
    [`#${number.format(p.rank.world)}`, `of ${number.format(p.rank.worldOf)}`, 'in the world'],
    [`#${p.rank.position}`, '', `of ${number.format(p.rank.positionOf)} ${p.position.toLowerCase()}s`],
    [`#${p.rank.club}`, '', `at ${p.club.name}`],
    [signed(p.change.season), '', 'this season'],
  ];
  field('ranks').replaceChildren(...rows.map(([value, small, label]) => {
    const div = document.createElement('div');
    div.innerHTML = `<dt>${escape(label)}</dt><dd>${value}${small ? ` <small>${small}</small>` : ''}</dd>`;
    return div;
  }));
}

function matchTitle(m) { return `${m.goalsFor}–${m.goalsAgainst} ${m.home ? 'vs' : 'at'} ${m.opponent}`; }

function renderSeason(p) {
  const h = p.history;
  const last = h[h.length - 1];
  field('season-summary').textContent = `${p.shortName}'s rating went from ${h[0].rating} to ${last.rating} this season; ${p.club.name}'s from ${h[0].clubRating} to ${last.clubRating}.`;
  lineChart(field('season-chart'), field('season-readout'), {
    dates: h.map((d) => d.date),
    series: [
      { label: p.shortName, cls: 'line-player', values: h.map((d) => d.rating), color: '#FFD66B' },
      { label: p.club.name, cls: 'line-club', values: h.map((d) => d.clubRating), color: '#A9BBD0' },
    ],
    band: [0, 1],
    moments: p.moments,
    idle: `Point at the chart to read any matchday. Today he adds <strong>${signed(last.rating - last.clubRating)}</strong> to ${escape(p.club.name)}'s ${number.format(last.clubRating)}.`,
    read: (i) => {
      const d = h[i];
      const m = p.matches[i];
      return `<strong>${longDate(d.date)}</strong>, ${escape(matchTitle(m))}. ${escape(p.shortName)} <span class="gold">${number.format(d.rating)}</span> (${signed(m.change)}), `
        + `${escape(p.club.name)} ${number.format(d.clubRating)}: he adds ${signed(d.rating - d.clubRating)}.`;
    },
  });
}

/* If he moved: his club's rating is swapped for another club's; selection as chosen; the rest unchanged.
   Rotation and bench use the selection bonus a typical rotation or bench player gets (400 × share gap). */
async function renderTransfer(p) {
  const clubs = await getClubs();
  const select = field('transfer-club');
  const byLeague = {};
  clubs.filter((c) => c.id !== p.club.id).forEach((c) => (byLeague[c.league.name] ||= []).push(c));
  const rumoured = clubs.filter((c) => p.rumours.includes(c.id));
  select.innerHTML = (rumoured.length ? `<optgroup label="Rumoured">${rumoured.map((c) => `<option value="${c.id}">${escape(c.name)} (${number.format(c.rating)})</option>`).join('')}</optgroup>` : '')
    + Object.entries(byLeague).map(([league, list]) => `<optgroup label="${escape(league)}">${list.map((c) => `<option value="${c.id}">${escape(c.name)} (${number.format(c.rating)})</option>`).join('')}</optgroup>`).join('');
  const strongest = clubs.find((c) => c.id !== p.club.id);
  select.value = (rumoured[0] || strongest).id;
  field('rumours').innerHTML = rumoured.length
    ? `<span>Linked with</span>${rumoured.map((c) => `<button type="button" class="rumour" data-club="${c.id}" aria-pressed="false">${escape(c.name)}</button>`).join('')}`
    : '';
  const parts = Object.fromEntries(p.parts.map((x) => [x.key, x.value]));
  const selectionFor = { same: parts.selection, rotation: Math.min(parts.selection, -110), bench: Math.min(parts.selection, -230) };
  let role = 'same';
  const update = () => {
    const club = clubs.find((c) => c.id === select.value);
    const selection = selectionFor[role];
    const rest = parts.goals + parts.national + parts.absence;
    const projected = club.rating + selection + rest;
    const change = projected - p.rating;
    field('transfer-sum').innerHTML = `<span class="club">${number.format(club.rating)}</span><span class="op">${escape(club.name)}</span>`
      + `<span>${signed(selection)}</span><span class="op">${role === 'same' ? 'as now' : role}</span>`
      + `<span>${signed(rest)}</span><span class="op">the rest</span><span class="op">=</span>`
      + `<span class="projected">${number.format(projected)}</span><span class="${direction(change)}">${signed(change)}</span>`
      + `<small>${change >= 0 ? 'Up' : 'Down'} ${Math.abs(change)} from today's ${number.format(p.rating)}, ${club.rating > p.club.rating ? 'a step up' : 'a step down'} from ${escape(p.club.name)} (${number.format(p.club.rating)}).</small>`;
    document.querySelectorAll('.rumour').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.club === select.value)));
  };
  select.addEventListener('change', update);
  field('rumours').addEventListener('click', (event) => {
    const button = event.target.closest('.rumour');
    if (button) { select.value = button.dataset.club; update(); }
  });
  field('transfer-role').addEventListener('click', (event) => {
    const button = event.target.closest('[data-role]');
    if (!button) return;
    role = button.dataset.role;
    field('transfer-role').querySelectorAll('button').forEach((b) => b.setAttribute('aria-checked', String(b === button)));
    update();
  });
  update();
}

function renderPrice(p) {
  const credits = (v) => `${v.toFixed(2)} cr`;
  const first = p.price[0].price;
  const last = p.price[p.price.length - 1].price;
  lineChart(field('price-chart'), field('price-readout'), {
    dates: p.price.map((d) => d.date),
    series: [{ label: 'Price', cls: 'line-price', values: p.price.map((d) => d.price), color: '#5AA9FF' }],
    format: (v) => v.toFixed(v < 10 ? 2 : 1),
    idle: `Simulated price today <strong>${credits(last)}</strong>, ${signed(Math.round((last / first - 1) * 100))}% this season.`,
    read: (i) => `<strong>${shortDate(p.price[i].date)}</strong>: ${credits(p.price[i].price)} a share, rating ${number.format(p.history[i].rating)}.`,
  });
}

function renderMatches(p, count) {
  const shown = (count === 'all' ? p.matches : p.matches.slice(-count)).slice().reverse();
  field('matches').replaceChildren(...shown.map((m) => {
    const li = document.createElement('li');
    li.className = 'match';
    if (!m.listed) li.dataset.out = '';
    const role = !m.listed ? 'Not in the squad' : m.started ? `Started, ${m.minutes} min` : m.minutes ? `Came on, ${m.minutes} min` : 'Unused substitute';
    li.innerHTML = `<span class="match-date">${shortDate(m.date)}</span>
      <span class="match-main"><span class="match-title"><span class="score">${m.goalsFor}–${m.goalsAgainst}</span>${m.home ? 'vs' : 'at'} ${escape(m.opponent)}<span class="match-note">${escape(m.note || role)}</span></span></span>
      <span class="minutes" aria-label="${role}"><span>${m.listed ? `${m.minutes}′` : 'Out'}</span><span class="minutes-bar"><i style="width:${(Math.min(m.minutes, 90) / 90) * 100}%"></i></span></span>
      <span class="change ${direction(m.change)}" aria-label="Rating change ${signed(m.change)}">${signed(m.change)}</span>`;
    return li;
  }));
  document.querySelectorAll('[data-range]').forEach((button) => {
    button.setAttribute('aria-checked', String(button.dataset.range === String(count)));
    button.onclick = () => renderMatches(p, button.dataset.range === 'all' ? 'all' : +button.dataset.range);
  });
}

function renderHow(p) {
  field('how').replaceChildren(...p.parts.map((part, i) => {
    const li = document.createElement('li');
    li.innerHTML = `<span class="v ${part.key === 'club' ? 'club' : part.value < 0 ? 'minus' : ''}">${partValue(part, i)}</span>`
      + `<span class="t"><strong>${escape(part.label)}.</strong> ${escape(part.explain)}</span>`;
    return li;
  }));
}

function renderNeighbours(p) {
  field('neighbours').replaceChildren(...p.neighbours.map((n) => {
    const li = document.createElement('li');
    if (n.id === p.id) li.setAttribute('aria-current', 'true');
    li.innerHTML = `<span class="r">#${n.rank}</span><span class="n">${n.id === p.id ? `<strong>${escape(n.name)}</strong>` : `<a href="${playerUrl(n.id)}">${escape(n.name)}</a>`}<small>${escape(n.club)}</small></span><span class="e">${number.format(n.rating)}</span>`;
    return li;
  }));
}

function wireShare(p) {
  const button = document.querySelector('[data-action="share"]');
  button.addEventListener('click', async () => {
    try {
      if (navigator.share) { await navigator.share({ title: document.title, text: `${p.name} is rated ${number.format(p.rating)} on OpenElo`, url: location.href }); return; }
      await navigator.clipboard.writeText(location.href);
      button.textContent = 'Link copied';
    } catch {
      button.textContent = 'Copy the address bar to share';
    }
    setTimeout(() => { button.textContent = 'Share'; }, 2400);
  });
}

/* Behind the page: his season against his club's in particles (gold and silver) beside the hero, which
   gather into a football mid-page and settle over the pitch at the end. The camera flies with them. */
async function buildScene(p) {
  immersive({
    formations: [
      curveFormation([{ values: p.history.map((d) => d.rating), weight: 1.5 }, { values: p.history.map((d) => d.clubRating), weight: 0.8, alt: true }],
        { from: [-3.5, -0.3, 3], to: [8.5, -0.3, -7], height: 6.2 }),
      await textFormation(number.format(p.rating), { center: [0, 3.2, -2], width: 13 }),
      fieldFormation(),
    ],
    palette: ['#FFD66B', '#FFD66B', '#7FA7D8'],
    next: { href: clubUrl(p.club.id), label: p.club.name },
    keyframes: [
      { at: 0, morph: 0, pos: [-2, 3.2, 21], look: [-2.2, 2.6, -2] },
      { at: 0.12, morph: 0, pos: [1, 3.8, 18], look: [-1.8, 2.6, -2] },
      { at: '#stage-rating', morph: 1, pos: [0, 3.3, 15], look: [0, 2.4, -2], shift: 0 },
      { at: '#season-title', morph: 1, pos: [-3, 4.6, 17], look: [0, 3, -3] },
      { at: 0.8, morph: 2, pos: [0, 10, 26], look: [0, 0, -12] },
      { at: 1, morph: 2, pos: [-7, 6, 16], look: [0, 1, -22] },
    ],
  });
}
