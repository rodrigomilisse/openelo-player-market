// Pre-rendered pages: the site's own templates with the page's facts written into the HTML, plus a plain summary
// section that stays visible to everyone. The page script then runs as usual and draws the charts and scene.
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = new Intl.NumberFormat('en-GB');
const fmt = (n) => num.format(Math.round(n));
const signed = (v) => (v > 0 ? `+${fmt(v)}` : v < 0 ? `−${fmt(-v)}` : '0');
const slug = (s) => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
const longDate = (iso) => new Date(`${iso}T12:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
const shortDate = (iso) => new Date(`${iso}T12:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
const trim = (s, n = 158) => (s.length <= n ? s : `${s.slice(0, n - 1).replace(/\s+\S*$/, '')}…`);

export const playerFile = (id) => `player-${id}.html`;
export const clubFile = (id) => `club-${id}.html`;
const pl = (id) => playerFile(id);
const cl = (id) => clubFile(id);

/* A player's page ranks only with enough recent appearances; others still exist (the site links to them) but are noindex. */
export function appearances(player, asOf, windowDays) {
  const from = new Date(`${asOf}T12:00:00Z`).getTime() - windowDays * 86400000;
  return (player.matches || []).filter((m) => m.listed && new Date(`${m.date}T12:00:00Z`).getTime() >= from).length;
}

const table = (head, rows, { num: numCols = [] } = {}) => `<div class="table-wrap"><table><thead><tr>${head.map((h, i) => `<th${numCols.includes(i) ? ' class="num"' : ''}>${h}</th>`).join('')}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c, i) => `<td${numCols.includes(i) ? ' class="num"' : ''}>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
const matchRows = (ms) => ms.slice(-5).reverse().map((m) => [shortDate(m.date), `${m.home ? 'vs' : 'at'} ${esc(m.opponent)}`, `${m.goalsFor}–${m.goalsAgainst}`, m.listed ? (m.started ? 'Started' : 'Substitute') : 'Not in squad', signed(m.change)]);

/* ---------- head rewriting ---------- */
export function setHead(html, { title, description, image }) {
  let out = html.replace(/<title>[^<]*<\/title>/, `<title>${esc(title)}</title>`)
    .replace(/(<meta name="description" content=")[^"]*(")/, `$1${esc(description)}$2`)
    .replace(/(<meta property="og:title" content=")[^"]*(")/, `$1${esc(title)}$2`)
    .replace(/(<meta property="og:description" content=")[^"]*(")/, `$1${esc(description)}$2`);
  if (image) out = out.replace(/(<meta property="og:image" content=")[^"]*(")/, `$1${esc(image)}$2`);
  return out;
}
const must = (html, needle) => { if (!html.includes(needle)) throw new Error(`template changed: cannot find ${needle.slice(0, 60)}`); return html; };
const before = (html, marker, insert) => must(html, marker).replace(marker, `${insert}\n    ${marker}`);

/* ---------- players ---------- */
export function playerPage(template, p, { source }) {
  const rank = p.rank || {};
  const title = `${p.name} rating: ${fmt(p.rating)}${rank.world ? ` (#${rank.world})` : ''} | OpenElo`;
  const description = trim(`${p.name} (${p.club.name}, ${p.position.toLowerCase()}) is rated ${fmt(p.rating)} on OpenElo${rank.world ? `, ${rank.world} of ${fmt(rank.worldOf)} rated players` : ''}. ${p.change ? `${signed(p.change.season)} this season. ` : ''}Built only from match results and minutes played.`);
  const identity = [`<a href="${cl(p.club.id)}">${esc(p.club.name)}</a>`, esc(p.position.toLowerCase()), p.age, p.nation && esc(p.nation)].filter(Boolean).join(', ');
  let html = setHead(template, { title, description });
  html = must(html, '<body class="player-page">').replace('<body class="player-page">', `<body class="player-page" data-id="${esc(p.id)}" data-source="${source}">`);
  html = html.replace('<span class="nameplate-surname" data-field="surname"></span>', `<span class="nameplate-surname" data-field="surname">${esc(p.shortName || p.name)}</span>`)
    .replace('<p class="identity" data-field="identity"></p>', `<p class="identity" data-field="identity">${identity}</p>`)
    .replace('<h1 id="player-name" data-field="name"></h1>', `<h1 id="player-name" data-field="name">${esc(p.name)}</h1>`)
    .replace('<span class="total-value" data-field="rating"></span>', `<span class="total-value" data-field="rating">${fmt(p.rating)}</span>`);
  const parts = (p.parts || []).map((x) => [esc(x.label || x.key), signed(x.value)]);
  const summary = `<section class="glass-panel seo-summary" aria-labelledby="summary-title">
      <h2 id="summary-title">${esc(p.name)}'s OpenElo rating</h2>
      <p>${esc(p.name)} plays${p.position ? ` as a ${esc(p.position.toLowerCase())}` : ''} for <a href="${cl(p.club.id)}">${esc(p.club.name)}</a> (${esc(p.club.league?.name || '')}). His OpenElo rating on ${longDate(p.asOf)} is <strong>${fmt(p.rating)}</strong>${rank.world ? `, ${rank.world} of ${fmt(rank.worldOf)} rated players` : ''}${rank.club ? ` and ${rank.club} of ${rank.clubOf} at his club` : ''}. ${p.change ? `It moved ${signed(p.change.lastMatch)} in his last match and ${signed(p.change.season)} this season.` : ''}</p>
      <p>The rating is his club's rating plus what he adds himself, from starting, scoring and national-team selection, minus any absence. Only results and minutes go in. <a href="how.html">How OpenElo works</a>.</p>
      ${parts.length ? table(['Part', 'Points'], parts, { num: [1] }) : ''}
      ${(p.matches || []).length ? `<h2>Last matches</h2>${table(['Date', 'Match', 'Score', 'Role', 'Change'], matchRows(p.matches), { num: [4] })}` : ''}
      ${(p.neighbours || []).length ? `<h2>Rated nearby</h2><ul>${p.neighbours.map((n) => `<li>#${n.rank} <a href="${pl(n.id)}">${esc(n.name)}</a> (${esc(n.club)}), ${fmt(n.rating)}</li>`).join('')}</ul>` : ''}
    </section>`;
  html = before(html, '<section class="stage" id="stage-rating"', summary);
  return { html, title, description, jsonld: [person(p), crumbs([['OpenElo', ''], ['Rankings', 'rankings-world-1.html'], [p.name, pl(p.id)]])] };
}
const person = (p) => ({ '@type': 'Person', name: p.name, jobTitle: 'Footballer', ...(p.nation ? { nationality: p.nation } : {}), memberOf: { '@type': 'SportsTeam', name: p.club.name } });
const crumbs = (items) => ({ '@type': 'BreadcrumbList', itemListElement: items.map(([name, file], i) => ({ '@type': 'ListItem', position: i + 1, name, item: { file } })) });

/* ---------- clubs ---------- */
export function clubPage(template, c, { source }) {
  const title = `${c.name} rating: ${fmt(c.rating)} | OpenElo`;
  const description = trim(`${c.name} (${c.league?.name || ''}) is rated ${fmt(c.rating)} on OpenElo${c.rank?.world ? `, ${c.rank.world} of ${fmt(c.rank.worldOf)} clubs` : ''}. See who carries the squad, and the club's season.`);
  let html = setHead(template, { title, description });
  html = must(html, '<body').replace(/<body([^>]*)>/, `<body$1 data-id="${esc(c.id)}" data-source="${source}">`)
    .replace('<h1 id="club-name" data-field="name"></h1>', `<h1 id="club-name" data-field="name">${esc(c.name)}</h1>`)
    .replace('<p class="big" data-field="rating"></p>', `<p class="big" data-field="rating">${fmt(c.rating)}</p>`);
  const squad = (c.squad || []).slice(0, 15).map((p) => [`<a href="${pl(p.id)}">${esc(p.name)}</a>`, esc((p.position || '').toLowerCase()), fmt(p.rating), signed(p.gap)]);
  const summary = `<section class="glass-panel seo-summary" aria-labelledby="summary-title">
      <h2 id="summary-title">${esc(c.name)}'s OpenElo rating</h2>
      <p>${esc(c.name)} (${esc(c.league?.name || '')}) is rated <strong>${fmt(c.rating)}</strong> on OpenElo on ${longDate(c.asOf)}${c.rank?.world ? `, ${c.rank.world} of ${fmt(c.rank.worldOf)} clubs` : ''}${c.rank?.league ? ` and ${c.rank.league} of ${c.rank.leagueOf} in its league` : ''}. The gap column shows how far each player's own rating sits above or below the club's.</p>
      ${squad.length ? `<h2>Who carries the team</h2>${table(['Player', 'Position', 'Rating', 'Gap to club'], squad, { num: [2, 3] })}` : ''}
      ${(c.matches || []).length ? `<h2>Last results</h2>${table(['Date', 'Match', 'Score', 'Change'], (c.matches || []).slice(-5).reverse().map((m) => [shortDate(m.date), `${m.home ? 'vs' : 'at'} ${esc(m.opponent)}`, `${m.goalsFor}–${m.goalsAgainst}`, signed(m.change)]), { num: [3] })}` : ''}
    </section>`;
  html = before(html, '<section class="stage" id="stage-squad"', summary);
  return { html, title, description, jsonld: [{ '@type': 'SportsTeam', name: c.name, sport: 'Soccer' }, crumbs([['OpenElo', ''], ['Leagues', 'leagues.html'], [c.name, cl(c.id)]])] };
}

/* ---------- generated list pages (built from about.html's frame) ---------- */
function framed(about, { title, description, h1, lede, body, nextHref, nextLabel }) {
  let html = setHead(about, { title, description });
  html = html.replace(/<main>[\s\S]*<\/main>/, `<main>
    <section class="page-head" aria-labelledby="page-title">
      <h1 id="page-title">${esc(h1)}</h1>
      <p class="lede">${esc(lede)}</p>
    </section>
    ${body}
  </main>`);
  if (nextHref) html = html.replace(/next: \{ href: '[^']*', label: '[^']*' \}/, `next: { href: '${nextHref}', label: '${esc(nextLabel)}' }`);
  return { html, title, description };
}
const panel = (inner) => `<section class="glass-panel seo-summary" style="max-width:none">${inner}</section>`;

export const POSITIONS = (rows) => [...new Set(rows.map((p) => p.position))].map((name) => ({ id: slug(name) + 's', name }));

export function rankingPages(about, eligible, asOf) {
  const rows = eligible;  // already sorted by rank
  const out = new Map();
  const scopes = [{ id: 'world', label: 'World', list: rows, what: 'all players' }];
  for (const l of [...new Map(rows.map((p) => [p.leagueId, p.league])).entries()]) scopes.push({ id: l[0], label: l[1], list: rows.filter((p) => p.leagueId === l[0]), what: `players in the ${l[1]}` });
  for (const pos of POSITIONS(rows)) scopes.push({ id: pos.id, label: pos.name + 's', list: rows.filter((p) => p.position === pos.name), what: `${pos.name.toLowerCase()}s` });
  const nav = scopes.map((s) => `<a href="rankings-${s.id}-1.html">${esc(s.label)}</a>`).join(' · ');
  for (const s of scopes) {
    const pages = Math.max(1, Math.ceil(s.list.length / 100));
    for (let n = 1; n <= pages; n++) {
      const slice = s.list.slice((n - 1) * 100, n * 100);
      const first = (n - 1) * 100 + 1;
      const title = `${s.label} player rankings${n > 1 ? `, page ${n}` : ''} | OpenElo`;
      const description = `${s.label === 'World' ? 'The highest-rated footballers in the world' : `The highest-rated ${s.what}`} by OpenElo, ranked ${first} to ${first + slice.length - 1}. Updated ${longDate(asOf)}.`;
      const pager = `<p>${n > 1 ? `<a href="rankings-${s.id}-${n - 1}.html">← Previous</a> ` : ''}Page ${n} of ${pages}${n < pages ? ` <a href="rankings-${s.id}-${n + 1}.html">Next →</a>` : ''}</p>`;
      const body = panel(`${table(['#', 'Player', 'Club', 'Position', 'Rating', 'Week'], slice.map((p, i) => [first + i, `<a href="${pl(p.id)}">${esc(p.name)}</a>`, `<a href="${cl(p.clubId)}">${esc(p.club)}</a>`, esc(p.position.toLowerCase()), fmt(p.rating), signed(p.week)]), { num: [0, 4, 5] })}${pager}<p>Other lists: ${nav}</p><p>Filter and sort every player on the <a href="rankings.html">rankings tool</a>.</p>`);
      out.set(`rankings-${s.id}-${n}.html`, { ...framed(about, { title, description, h1: `${s.label} player rankings`, lede: `Ranked by OpenElo as of ${longDate(asOf)}${n > 1 ? `, page ${n}` : ''}.`, body, nextHref: 'rankings.html', nextLabel: 'Rankings' }), jsonld: [crumbs([['OpenElo', ''], ['Rankings', `rankings-world-1.html`], [s.label, `rankings-${s.id}-${n}.html`]])], list: s.id });
    }
  }
  return out;
}

/* ---------- the matchday (week) ---------- */
export const weekBlock = (w, withHeading = true) => `${withHeading ? '' : ''}${w.story ? `<p><strong>${esc(w.story.title)}.</strong> ${esc(w.story.text)}</p>` : ''}
      <h2>Biggest risers</h2>${table(['Player', 'Club', 'Rating', 'Change'], (w.risers || []).map((r) => [`<a href="${pl(r.id)}">${esc(r.name)}</a>`, `<a href="${cl(r.clubId)}">${esc(r.club)}</a>`, fmt(r.rating), signed(r.change)]), { num: [2, 3] })}
      <h2>Biggest fallers</h2>${table(['Player', 'Club', 'Rating', 'Change'], (w.fallers || []).map((r) => [`<a href="${pl(r.id)}">${esc(r.name)}</a>`, `<a href="${cl(r.clubId)}">${esc(r.club)}</a>`, fmt(r.rating), signed(r.change)]), { num: [2, 3] })}
      <h2>The top ten</h2>${table(['Player', 'Club', 'Rating'], (w.top || []).map((r) => [`<a href="${pl(r.id)}">${esc(r.name)}</a>`, `<a href="${cl(r.clubId)}">${esc(r.club)}</a>`, fmt(r.rating)]), { num: [2] })}
      <h2>Clubs on the move</h2>${table(['Club', 'Rating', 'Change', 'Last match'], (w.clubs || []).map((c) => [`<a href="${cl(c.id)}">${esc(c.name)}</a>`, fmt(c.rating), signed(c.change), esc(c.note)]), { num: [1, 2] })}`;

export function weekPage(about, w) {
  const title = `Player ratings, week of ${longDate(w.asOf)} | OpenElo`;
  const description = trim(`${w.story ? `${w.story.title}. ` : ''}The biggest risers and fallers in player ratings after the matchday of ${longDate(w.asOf)}.`);
  return { ...framed(about, { title, description, h1: `Week of ${longDate(w.asOf)}`, lede: 'Who rose, who fell, and the top ten, from the matches played.', body: panel(weekBlock(w)), nextHref: 'index.html', nextLabel: 'This week' }),
    jsonld: [crumbs([['OpenElo', ''], ['This week', 'index.html'], [title, `week-${w.asOf}.html`]])] };
}

/* ---------- summaries added to existing pages ---------- */
export function withSummary(html, inner) { return before(html, '</main>', `<section class="glass-panel seo-summary" style="max-width:none">${inner}</section>`).replace(/\n    <\/main>/, '\n  </main>'); }
export const indexSummary = (w) => `<h2>This week in player ratings</h2>${weekBlock(w)}`;
export const leaguesSummary = (lg) => `<h2>Leagues by average club rating</h2>${lg.leagues.map((l) => `<h2>${esc(l.name)} (${esc(l.country)}), average ${fmt(l.rating)}</h2>${table(['Club', 'Rating', 'Week'], l.clubs.map((c) => [`<a href="${cl(c.id)}">${esc(c.name)}</a>`, fmt(c.rating), signed(c.week)]), { num: [1, 2] })}`).join('')}`;
