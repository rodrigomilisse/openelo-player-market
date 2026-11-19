// Player page. Reads one player in the read-API shape (see README.md) and renders it.
import { THREE, COLOR, createStage, addStadium, addRibbon, glowSprite, scrollTracker, pointerTracker, smoothstep, reducedMotion } from '../design/stadium.js';

const params = new URLSearchParams(location.search);
const id = (params.get('id') || 'tiago-mendonca').replace(/[^a-z0-9-]/g, '');
const field = (name) => document.querySelector(`[data-field="${name}"]`);
const number = new Intl.NumberFormat('en-GB');
const signed = (v) => (v > 0 ? `+${number.format(v)}` : v < 0 ? `−${number.format(-v)}` : '0');
const shortDate = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' });
const longDate = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
const asDate = (iso) => new Date(`${iso}T12:00:00Z`);

const response = await fetch(`data/players/${id}.json`);
if (!response.ok) {
  field('name').textContent = 'Player not found';
  field('identity').textContent = 'No player has this address. Check the link, or find him in the rankings.';
  throw new Error(`player ${id}: ${response.status}`);
}
const player = await response.json();
render(player);
buildScene(player);

function render(p) {
  document.title = `${p.name}: ${number.format(p.rating)} OpenElo`;
  field('sample').hidden = !p.sample;
  field('surname').textContent = p.shortName;
  fitSurname();
  field('identity').textContent = `${p.club.name}, ${p.position.toLowerCase()}, ${p.age}`;
  field('name').textContent = p.name;
  field('legend-player').textContent = p.shortName;
  field('legend-club').textContent = p.club.name;
  field('waitlist-title').textContent = `Back ${p.shortName}'s rating when the market opens`;
  field('formula').textContent = `Rated with ${p.formula}, as of ${longDate.format(asDate(p.asOf))}.`;
  field('footer').textContent = 'OpenElo rates players from public match results and minutes played. '
    + 'Ratings are not a valuation, a transfer fee or an offer of anything.';
  renderEquation(p);
  renderRanks(p);
  renderChart(p);
  renderMatches(p, 10);
  renderHow(p);
  renderNeighbours(p);
  wireShare(p);
  wireWaitlist();
}

/* The surname fills the nameplate's height (desktop) without running off it. */
function fitSurname() {
  const el = field('surname');
  const fit = () => {
    el.style.fontSize = '';
    if (window.innerWidth <= 860) return;
    const plate = el.parentElement.getBoundingClientRect();
    const size = parseFloat(getComputedStyle(el).fontSize);
    const room = plate.height * 0.94;
    el.style.fontSize = `${Math.min(size, size * (room / el.offsetHeight))}px`;   // vertical text: its length is its height
  };
  document.fonts.ready.then(fit);
  window.addEventListener('resize', fit);
}

/* The equation: club + what he adds = OpenElo. Each part explains itself. */
function renderEquation(p) {
  const list = field('parts');
  const explain = field('explain');
  const defaultText = `Tap a number to see where it comes from. Together they make <strong>${number.format(p.rating)}</strong>.`;
  explain.innerHTML = defaultText;
  list.replaceChildren(...p.parts.map((part, i) => {
    const li = document.createElement('li');
    li.className = 'part';
    li.dataset.key = part.key;
    li.dataset.sign = part.value < 0 ? 'minus' : 'plus';
    li.style.setProperty('--i', i);
    const shown = i === 0 ? number.format(part.value) : signed(part.value);
    li.innerHTML = `<button type="button" aria-pressed="false"><span class="part-value" data-to="${part.value}" data-first="${i === 0}">${shown}</span>`
      + `<span class="part-label">${part.label}</span></button>`;
    li.querySelector('button').addEventListener('click', (event) => {
      const button = event.currentTarget;
      const pressed = button.getAttribute('aria-pressed') === 'true';
      list.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', 'false'));
      button.setAttribute('aria-pressed', String(!pressed));
      explain.innerHTML = pressed ? defaultText : `<strong>${part.label}, ${i === 0 ? number.format(part.value) : signed(part.value)}.</strong> ${part.explain}`;
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
    [`#${p.rank.position}`, '', `of ${number.format(p.rank.positionOf)} ${p.position.toLowerCase()} players`],
    [signed(p.change.season), '', 'this season'],
  ];
  field('ranks').replaceChildren(...rows.map(([value, small, label]) => {
    const div = document.createElement('div');
    div.innerHTML = `<dt>${label}</dt><dd>${value}${small ? ` <small>${small}</small>` : ''}</dd>`;
    return div;
  }));
}

/* Season chart: his rating against his club's, the gap shaded, moments pinned. */
function renderChart(p) {
  const svg = document.querySelector('.chart-svg');
  const readout = field('readout');
  const h = p.history;
  const lo = Math.min(...h.map((d) => d.clubRating)) - 20;
  const hi = Math.max(...h.map((d) => d.rating)) + 20;
  const first = h[0];
  const last = h[h.length - 1];
  field('chart-summary').textContent = `${p.shortName}'s rating went from ${first.rating} to ${last.rating} this season; `
    + `${p.club.name}'s from ${first.clubRating} to ${last.clubRating}.`;

  function draw() {
    const width = svg.clientWidth;
    const height = svg.clientHeight;
    const pad = { l: 44, r: 12, t: 26, b: 28 };
    const x = (i) => pad.l + (i / (h.length - 1)) * (width - pad.l - pad.r);
    const y = (v) => pad.t + (1 - (v - lo) / (hi - lo)) * (height - pad.t - pad.b);
    const path = (key) => h.map((d, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(d[key]).toFixed(1)}`).join('');
    const gap = `${path('rating')}${h.map((d, i) => `L${x(h.length - 1 - i).toFixed(1)},${y(h[h.length - 1 - i].clubRating).toFixed(1)}`).join('')}Z`;
    const step = (hi - lo) > 300 ? 100 : 50;
    const ticks = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) ticks.push(v);
    const months = h.map((d, i) => [i, asDate(d.date)]).filter(([i, d], k, all) => k === 0 || d.getUTCMonth() !== all[k - 1][1].getUTCMonth());
    const moments = (p.moments || []).map((m) => [h.findIndex((d) => d.date === m.date), m]).filter(([i]) => i >= 0);
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.innerHTML = `
      <defs><linearGradient id="gapFill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#FFD66B" stop-opacity="0.22"/><stop offset="1" stop-color="#FFD66B" stop-opacity="0.04"/></linearGradient></defs>
      <g class="grid">${ticks.map((v) => `<line x1="${pad.l}" x2="${width - pad.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${pad.l - 8}" y="${y(v) + 4}" text-anchor="end">${number.format(v)}</text>`).join('')}</g>
      <g class="axis">${months.map(([i, d]) => `<text x="${x(i)}" y="${height - 6}" text-anchor="${i === 0 ? 'start' : 'middle'}">${d.toLocaleString('en-GB', { month: 'short', timeZone: 'UTC' })}</text>`).join('')}</g>
      <path class="gap" d="${gap}"/>
      <path class="club-line" d="${path('clubRating')}"/>
      <path class="player-line" d="${path('rating')}" pathLength="1"/>
      ${moments.map(([i, m], k) => `<g class="moment"><line x1="${x(i)}" x2="${x(i)}" y1="${pad.t - 6}" y2="${height - pad.b}"/>
        <circle cx="${x(i)}" cy="${y(h[i].rating)}" r="4.5"/>
        <text x="${x(i) + (i > h.length * 0.7 ? -8 : 8)}" y="${pad.t - 10 + (k % 2) * 0}" text-anchor="${i > h.length * 0.7 ? 'end' : 'start'}">${m.text}</text></g>`).join('')}
      <g class="cursor" visibility="hidden"><line y1="${pad.t}" y2="${height - pad.b}"/><circle r="5"/><circle class="club-dot" r="3.5"/></g>`;
    const cursor = svg.querySelector('.cursor');
    const show = (i) => {
      const d = h[i];
      const m = p.matches[i];
      cursor.setAttribute('visibility', 'visible');
      cursor.querySelector('line').setAttribute('x1', x(i));
      cursor.querySelector('line').setAttribute('x2', x(i));
      cursor.querySelector('circle').setAttribute('cx', x(i));
      cursor.querySelector('circle').setAttribute('cy', y(d.rating));
      cursor.querySelector('.club-dot').setAttribute('cx', x(i));
      cursor.querySelector('.club-dot').setAttribute('cy', y(d.clubRating));
      readout.innerHTML = `<strong>${longDate.format(asDate(d.date))}</strong>, ${matchTitle(m)}. `
        + `${p.shortName} <span class="gold">${number.format(d.rating)}</span> (${signed(m.change)}), `
        + `${p.club.name} ${number.format(d.clubRating)}: he adds ${signed(d.rating - d.clubRating)}.`;
    };
    const pick = (event) => {
      const box = svg.getBoundingClientRect();
      const i = Math.round(((event.clientX - box.left - pad.l) / (box.width - pad.l - pad.r)) * (h.length - 1));
      show(Math.max(0, Math.min(h.length - 1, i)));
    };
    svg.onpointermove = pick;
    svg.onpointerdown = pick;
    svg.onpointerleave = () => { cursor.setAttribute('visibility', 'hidden'); resetReadout(); };
  }
  const resetReadout = () => {
    readout.innerHTML = `Point at the chart to read any matchday. Today he adds <strong>${signed(last.rating - last.clubRating)}</strong> `
      + `to ${p.club.name}'s ${number.format(last.clubRating)}.`;
  };
  resetReadout();
  draw();
  new ResizeObserver(draw).observe(svg);
}

function matchTitle(m) {
  const where = m.home ? 'vs' : 'at';
  return `${m.goalsFor}–${m.goalsAgainst} ${where} ${m.opponent}`;
}

function renderMatches(p, count) {
  const list = field('matches');
  const shown = (count === 'all' ? p.matches : p.matches.slice(-count)).slice().reverse();
  list.replaceChildren(...shown.map((m) => {
    const li = document.createElement('li');
    li.className = 'match';
    if (!m.listed) li.dataset.out = '';
    const direction = m.change > 0 ? 'up' : m.change < 0 ? 'down' : 'flat';
    const role = !m.listed ? 'Not in the squad' : m.started ? `Started, ${m.minutes} min` : m.minutes ? `Came on, ${m.minutes} min` : 'Unused substitute';
    li.innerHTML = `
      <span class="match-date">${shortDate.format(asDate(m.date))}</span>
      <span class="match-main"><span class="match-title"><span class="score">${m.goalsFor}–${m.goalsAgainst}</span>${m.home ? 'vs' : 'at'} ${m.opponent}</span>
        <span class="match-note">${m.note || role}</span></span>
      <span class="minutes" aria-label="${role}"><span>${m.listed ? `${m.minutes}′` : 'Out'}</span><span class="minutes-bar"><i style="width:${(Math.min(m.minutes, 90) / 90) * 100}%"></i></span></span>
      <span class="change ${direction}" aria-label="Rating change ${signed(m.change)}">${signed(m.change)}</span>`;
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
    const cls = part.key === 'club' ? 'club' : part.value < 0 ? 'minus' : '';
    li.innerHTML = `<span class="v ${cls}">${i === 0 ? number.format(part.value) : signed(part.value)}</span>`
      + `<span class="t"><strong>${part.label}.</strong> ${part.explain}</span>`;
    return li;
  }));
}

function renderNeighbours(p) {
  field('neighbours').replaceChildren(...p.neighbours.map((n) => {
    const li = document.createElement('li');
    if (n.id === p.id) li.setAttribute('aria-current', 'true');
    const name = n.id === p.id ? `<strong>${n.name}</strong>` : `<a href="?id=${n.id}">${n.name}</a>`;
    li.innerHTML = `<span class="r">#${n.rank}</span><span class="n">${name}<small>${n.club}</small></span><span class="e">${number.format(n.rating)}</span>`;
    return li;
  }));
}

function wireShare(p) {
  const button = document.querySelector('[data-action="share"]');
  button.addEventListener('click', async () => {
    const data = { title: document.title, text: `${p.name} is rated ${number.format(p.rating)} on OpenElo`, url: location.href };
    try {
      if (navigator.share) { await navigator.share(data); return; }
      await navigator.clipboard.writeText(location.href);
      button.textContent = 'Link copied';
    } catch {
      button.textContent = 'Copy the address bar to share';
    }
    setTimeout(() => { button.textContent = 'Share'; }, 2400);
  });
}

function wireWaitlist() {
  // No backend yet: the form confirms locally. Wire it to the waitlist endpoint when it exists.
  const form = document.querySelector('[data-action="waitlist"]');
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    field('waitlist-status').textContent = `You're on the list. We'll email ${form.email.value} when the market opens.`;
    form.reset();
  });
}

/* Behind the page: the night stadium, his rating as a gold ribbon, his club's as a silver one. */
function buildScene(p) {
  const canvas = document.getElementById('scene');
  let stage;
  try {
    // shiftRight keeps the season in the open right half, clear of the hero text.
    stage = createStage(canvas, { shiftRight: 0.2, fog: 0.018 });
  } catch {
    canvas.remove();   // no WebGL: the page works without the scene
    return;
  }
  const STEP = 1.1;
  const ratings = p.history.map((d) => d.rating);
  const clubs = p.history.map((d) => d.clubRating);
  const lo = Math.min(...clubs) - 40;
  const hi = Math.max(...ratings) + 40;
  const toY = (v) => -0.6 + ((v - lo) / (hi - lo)) * 6.5;
  const length = (ratings.length - 1) * STEP;
  addStadium(stage, { centerZ: -length / 2, length: length + 10, crowd: 7000 });
  const gold = addRibbon(stage.scene, ratings, { toY, step: STEP, color: COLOR.elo, core: COLOR.eloCore, wiggle: 0.5, radius: 0.07 });
  const club = addRibbon(stage.scene, clubs, { toY, step: STEP, x: -3.2, color: 0xA9BBD0, core: 0xE4ECF5, wiggle: 0.5, radius: 0.035, curtain: false });
  const now = gold.points[gold.points.length - 1];
  const halo = glowSprite([255, 214, 107], 3.2);
  halo.position.copy(now);
  stage.scene.add(halo);

  const scroll = scrollTracker(0.06);
  const pointer = pointerTracker(0.05);
  const narrow = () => window.innerWidth <= 860;
  stage.start((time) => {
    const progress = reducedMotion ? 0 : scroll.step();
    const mouse = reducedMotion ? { x: 0, y: 0 } : pointer.step();
    // Standing just past today, low, looking back at August: the season climbs towards the viewer
    // and ends in the glow of today's rating. Scrolling pulls the camera back a little.
    const drift = smoothstep(0, 0.5, progress);
    stage.camera.position.set(5.5 + mouse.x * 1.5, 3 - mouse.y * 0.8, -length - 12 - drift * 6);
    stage.camera.lookAt(0, toY((lo + hi) / 2) + 2, -length * 0.3 - drift * 6);
    // The ribbons belong to the hero: they fade as the reader moves on to the details.
    const fade = 1 - 0.8 * smoothstep(0.08, 0.3, progress);
    gold.setOpacity(fade * (narrow() ? 0.4 : 1));
    club.setOpacity(fade * (narrow() ? 0.35 : 0.9));
    halo.material.opacity = fade * (0.75 + Math.sin(time * 2.2) * 0.2);
  });
}
