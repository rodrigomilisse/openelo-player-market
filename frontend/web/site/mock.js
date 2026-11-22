// Mock world for building the site: fictional leagues, clubs and players, one simulated season.
// Deterministic (seeded), generated in the browser, shaped exactly like the read API (README.md).
// The rating follows the real formula's structure (research/player_v2.py, the direct model):
//   rating = club rating + selection + goals and assists + national team − absence
// Nothing here is real. api.js swaps this out for real data when it exists.

const SEED = 20261119;
const START = Date.UTC(2025, 7, 16);   // first matchday
const DAY = 86400000;

function makeRandom(seed) {
  let s = seed | 0;
  return () => {
    s = (s + 0x6D2B79F5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const R = makeRandom(SEED);
const normal = (mean = 0, sd = 1) => { let u = 0; while (!u) u = R(); return mean + sd * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * R()); };
const pick = (list) => list[Math.floor(R() * list.length)];
const poisson = (lambda) => { let k = 0, p = 1; const l = Math.exp(-lambda); do { k++; p *= R(); } while (p > l); return k - 1; };
export const slug = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
const iso = (t) => new Date(t).toISOString().slice(0, 10);
const expected = (diff) => 1 / (1 + 10 ** (-diff / 400));

const NAMES = {
  pt: { first: ['Tiago', 'Rui', 'Nuno', 'João', 'Pedro', 'André', 'Diogo', 'Duarte', 'Gonçalo', 'Ivo', 'Bruno', 'Rafael', 'Miguel', 'Hugo', 'Tomás', 'Vasco', 'Fábio', 'Ricardo', 'Luís', 'Martim'],
    last: ['Arcanjo', 'Salgueiro', 'Baptista', 'Cotrim', 'Fontes', 'Valadas', 'Moura', 'Teixeira', 'Barros', 'Cardoso', 'Pinheiro', 'Quaresma', 'Lobo', 'Sequeira', 'Falcão', 'Amaral', 'Coutinho', 'Sobral', 'Rebelo', 'Brandão', 'Paixão', 'Gouveia', 'Raposo', 'Tavares'] },
  en: { first: ['Callum', 'Rhys', 'Owen', 'Liam', 'Jack', 'Harvey', 'Kieran', 'Ewan', 'Finn', 'Toby', 'Declan', 'Morgan', 'Lewis', 'Reece', 'Archie', 'Nathan', 'Elliot', 'Jamie', 'Connor', 'Ryan'],
    last: ['Ashworth', 'Pennington', 'Holloway', 'Blackwood', 'Fairclough', 'Thwaite', 'Marsden', 'Kershaw', 'Whitlock', 'Ainsworth', 'Haddon', 'Stanway', 'Lowther', 'Brindley', 'Calloway', 'Garside', 'Hartley', 'Rimmer', 'Sutcliffe', 'Dunmore', 'Ellery', 'Pryce'] },
  es: { first: ['Iker', 'Unai', 'Álvaro', 'Sergio', 'Pablo', 'Marcos', 'Rubén', 'Adrián', 'Javier', 'Mario', 'Óscar', 'Raúl', 'Gorka', 'Jon', 'Aitor', 'Dani', 'Nacho', 'Borja', 'Íñigo', 'Pau'],
    last: ['Arrieta', 'Zabala', 'Montoya', 'Quintero', 'Salcedo', 'Echeverría', 'Lozano', 'Barrena', 'Ocaña', 'Villalba', 'Mendizábal', 'Carrasco', 'Ibarra', 'Soler', 'Garmendia', 'Robles', 'Urquiza', 'Valcárcel', 'Aranda', 'Llorente'] },
};
const ABROAD = ['Brazil', 'France', 'Netherlands', 'Belgium', 'Uruguay', 'Ghana', 'Croatia', 'Denmark', 'Morocco', 'Colombia'];
const LEAGUES = [
  { id: 'northern-league', name: 'Northern League', country: 'England', names: 'en', level: 1765,
    clubs: ['Ashby Rovers', 'Calder Town', 'Harrowgate United', 'Kestrel Athletic', 'Marlow Vale', 'Northfleet City', 'Pennine Wanderers', 'Redcliffe FC', 'Saltmarsh Albion', 'Thornbury Town', 'Wexford Park', 'Whitby Forge'] },
  { id: 'liga-iberica', name: 'Liga Ibérica', country: 'Spain', names: 'es', level: 1735,
    clubs: ['CD Almenara', 'Atlético Ribera', 'Real Sierra Alta', 'Racing Valcárcel', 'Deportivo Arenal', 'SD Peñaclara', 'UD Lagunas', 'Real Olmeda', 'CD Mareas', 'Atlético Cierzo', 'CF Alcores', 'UD Brezo'] },
  { id: 'liga-atlantica', name: 'Liga Atlântica', country: 'Portugal', names: 'pt', level: 1690,
    clubs: ['Vale do Sado FC', 'Sporting Arade', 'União Litoral', 'Atlético Serrano', 'CD Ribamar', 'FC Alcantil', 'Académica do Vale', 'Estrela da Ria', 'Juventude Barrosa', 'SC Penedo', 'Desportivo Tejo', 'Lusitânia Norte'] },
];
const SQUAD = [['Goalkeeper', 2], ['Defender', 7], ['Midfielder', 7], ['Forward', 6]];
const GOAL_RATE = { Goalkeeper: 0, Defender: 0.04, Midfielder: 0.1, Forward: 0.3 };
const ASSIST_RATE = { Goalkeeper: 0.005, Defender: 0.06, Midfielder: 0.13, Forward: 0.14 };
const WINDOW = 50;
const AWAY = 1 - Math.exp(-7 / 120);   // absence: each missed match closes this share of the gap to 120

function roundRobin(teams) {
  const list = teams.slice();
  const rounds = [];
  for (let r = 0; r < list.length - 1; r++) {
    const pairs = [];
    for (let i = 0; i < list.length / 2; i++) {
      const a = list[i], b = list[list.length - 1 - i];
      pairs.push(r % 2 ? [b, a] : [a, b]);
    }
    rounds.push(pairs);
    list.splice(1, 0, list.pop());
  }
  return rounds.concat(rounds.map((round) => round.map(([a, b]) => [b, a])));
}

function build() {
  const clubs = [];
  const players = [];
  const used = new Set();
  for (const league of LEAGUES) {
    for (const name of league.clubs) {
      const club = { id: slug(name), name, league, rating: league.level + normal(0, 65), history: [], matches: [], squad: [], points: 0, gd: 0 };
      clubs.push(club);
      const pool = NAMES[league.names];
      for (const [position, count] of SQUAD) {
        for (let k = 0; k < count; k++) {
          let full;
          do { full = `${pick(pool.first)} ${pick(pool.last)}`; } while (used.has(full));
          used.add(full);
          const roll = k / count;
          const role = position === 'Goalkeeper' ? (k === 0 ? 'regular' : 'fringe') : roll < 0.5 ? 'regular' : roll < 0.78 ? 'rotation' : 'fringe';
          const player = { name: full, position, role, club, age: Math.round(18 + R() * 16),
            nation: R() < 0.72 ? league.country : pick(ABROAD), window: [], output: [], absence: 0, out: 0,
            national: 0, history: [], matches: [], moments: [], breakthrough: role === 'fringe' && R() < 0.25 };
          if (role === 'regular' && R() < 0.4) player.national = Math.max(0, normal(28, 14));
          // last season's squads seed the windows, so ratings start settled
          for (let i = 0; i < 30; i++) {
            const share = shareFor(player, i < 30);
            player.window.push(share);
            player.output.push([share * 90, R() < GOAL_RATE[position] * share ? 1 : 0, R() < ASSIST_RATE[position] * share ? 1 : 0]);
          }
          club.squad.push(player);
          players.push(player);
        }
      }
    }
  }
  // Vale do Sado's first midfielder keeps the name of the design prototypes' player.
  const vale = clubs.find((c) => c.id === 'vale-do-sado-fc');
  const tiago = vale.squad.find((p) => p.position === 'Midfielder' && p.role === 'regular');
  used.delete(tiago.name);
  Object.assign(tiago, { name: 'Tiago Mendonça', age: 24, nation: 'Portugal', national: 26 });

  const byLeague = LEAGUES.map((l) => clubs.filter((c) => c.league === l));
  const schedules = byLeague.map((list) => roundRobin(list));
  const rounds = schedules[0].length;
  for (let r = 0; r < rounds; r++) {
    const date = START + r * 7 * DAY + (r > 15 ? 3 * DAY : 0);
    for (const schedule of schedules) {
      for (const [home, away] of schedule[r]) playMatch(home, away, iso(date), r);
    }
    // international breaks: regulars of strong clubs get called up
    if ([3, 8, 14].includes(r)) {
      for (const p of players) {
        if (p.role === 'regular' && (p.national > 0 || (p.breakthrough && p.window.slice(-8).reduce((a, b) => a + b, 0) > 5) || R() < 0.015)) {
          if (!p.national) p.moments.push({ date: iso(date), kind: 'callup', text: `First ${p.nation} call-up` });
          p.national = Math.min(80, p.national + 9 + R() * 6);
        }
      }
    }
  }
  return { clubs, players, rounds };

  function shareFor(player, seeding) {
    const base = { regular: 0.9, rotation: 0.48, fringe: 0.2 }[player.role];
    const grow = player.breakthrough && !seeding ? Math.min(0.75, player.matches.length * 0.035) : 0;
    const share = base + grow + normal(0, 0.12);
    return Math.max(0, Math.min(1, share));
  }

  function playMatch(home, away, date, round) {
    const e = expected(home.rating + 50 - away.rating);
    const hg = poisson(0.6 + 1.6 * e), ag = poisson(0.6 + 1.6 * (1 - e));
    const score = hg > ag ? 1 : hg < ag ? 0 : 0.5;
    const margin = Math.abs(hg - ag) <= 1 ? 1 : Math.abs(hg - ag) === 2 ? 1.5 : (11 + Math.abs(hg - ag)) / 8;
    const swing = 22 * margin * (score - e);
    for (const [club, other, gf, ga, home_] of [[home, away, hg, ag, true], [away, home, ag, hg, false]]) {
      club.rating += home_ ? swing : -swing;
      club.points += gf > ga ? 3 : gf === ga ? 1 : 0;
      club.gd += gf - ga;
      club.history.push({ date, rating: Math.round(club.rating) });
      club.matches.push({ date, opponent: other.name, opponentId: other.id, home: home_, goalsFor: gf, goalsAgainst: ga,
        change: Math.round(home_ ? swing : -swing), rating: Math.round(club.rating) });
      playersOf(club, gf, date, round);
    }
  }

  function playersOf(club, goalsFor, date, round) {
    // the club's reference share: the mean of its 16 most-used players
    const shares = club.squad.map((p) => avg(p.window)).sort((a, b) => b - a).slice(0, 16);
    const reference = avg(shares);
    let goalsLeft = goalsFor;
    const scorers = club.squad.filter((p) => p.position !== 'Goalkeeper');
    for (const p of club.squad) {
      const before = p.history.length ? p.history[p.history.length - 1].rating : null;
      if (!p.out && R() < 0.012) {
        p.out = 1 + Math.floor(R() * 4);
        p.moments.push({ date, kind: 'absence', text: `Injured, ${p.out} ${p.out === 1 ? 'match' : 'matches'} out` });
      }
      const m = { date, opponent: club.matches[club.matches.length - 1].opponent, home: club.matches[club.matches.length - 1].home,
        goalsFor: club.matches[club.matches.length - 1].goalsFor, goalsAgainst: club.matches[club.matches.length - 1].goalsAgainst };
      if (p.out) {
        p.out -= 1;
        p.absence += (120 - p.absence) * AWAY;
        Object.assign(m, { listed: false, started: false, minutes: 0, goals: 0, assists: 0, note: 'Out injured' });
        if (!p.out) p.moments.push({ date, kind: 'return', text: 'Back from injury' });
      } else {
        const share = shareFor(p, false);
        const started = share > 0.6;
        const minutes = started ? (share > 0.9 ? 90 : Math.round(60 + share * 28)) : share > 0.15 ? Math.round(share * 60) : 0;
        let goals = 0, assists = 0;
        if (minutes && goalsLeft > 0 && R() < GOAL_RATE[p.position] * (minutes / 90) * (goalsFor + 0.5)) { goals = 1; goalsLeft -= 1; }
        if (minutes && R() < ASSIST_RATE[p.position] * (minutes / 90) * (goalsFor + 0.3)) assists = 1;
        p.window.push(started ? 1 : minutes / 90);
        p.output.push([minutes, goals, assists]);
        p.absence *= 0.5 ** (started ? 1 : minutes / 90);
        if (p.breakthrough && started && !p.moments.some((x) => x.kind === 'breakthrough')) {
          p.moments.push({ date, kind: 'breakthrough', text: 'Into the starting eleven' });
        }
        Object.assign(m, { listed: true, started, minutes, goals, assists,
          note: goals && assists ? 'Scored and set one up' : goals ? 'Scored' : assists ? 'Assist' : undefined });
      }
      if (p.window.length > WINDOW) p.window.shift();
      if (p.output.length > WINDOW) p.output.shift();
      const parts = partsOf(p, club, reference);
      const rating = Math.round(parts.reduce((s, x) => s + x.value, 0));
      m.change = before === null ? 0 : rating - before;
      m.rating = rating;
      m.clubRating = Math.round(club.rating);
      p.matches.push(m);
      p.history.push({ date, rating, clubRating: Math.round(club.rating) });
      p.parts = parts;
      p.reference = reference;
    }
  }
}

function avg(list) { return list.length ? list.reduce((a, b) => a + b, 0) / list.length : 0; }

function partsOf(p, club, reference) {
  const share = avg(p.window);
  const minutes = p.output.reduce((s, x) => s + x[0], 0);
  const goals = p.output.reduce((s, x) => s + x[1], 0);
  const assists = p.output.reduce((s, x) => s + x[2], 0);
  const ref = p.position === 'Goalkeeper' ? 1 : reference;
  const selection = 400 * (share - ref);
  const output = (100 * goals + 100 * assists) / (minutes / 90 + 5);
  const starts = p.window.filter((s) => s === 1).length;
  return [
    { key: 'club', value: Math.round(club.rating), label: club.name,
      explain: 'His club\'s rating after its last match. Every player starts from his team: OpenElo rates teams from results, then adjusts for each player.' },
    { key: 'selection', value: Math.round(selection), label: selection >= 40 ? 'Regular starter' : selection > -40 ? 'In and out of the side' : 'Mostly on the bench',
      explain: `He started ${starts} of his last ${p.window.length} matchday squads. ${selection >= 0 ? 'That is more' : 'That is less'} than ${club.name}'s ${p.position === 'Goalkeeper' ? 'standard for a first-choice keeper' : '16 most-used players play on average'}.` },
    { key: 'goals', value: Math.round(output), label: 'Goals and assists',
      explain: `${goals} goals and ${assists} assists in his last ${p.output.length} squads, per 90 minutes, with 5 scoreless matches added so a few lucky minutes can't carry it.` },
    { key: 'national', value: Math.round(p.national), label: p.national ? `${p.nation} call-ups` : 'No national call-ups',
      explain: p.national ? `Picked in ${p.nation}'s recent squads. Being selected by a strong national team adds points; not being picked never takes any away.` : 'Not picked for his national team recently. That never costs points; selection only adds.' },
    { key: 'absence', value: -Math.round(p.absence), label: p.absence >= 1 ? 'Recent absence' : 'No recent absence',
      explain: p.absence >= 1 ? 'Matches missed recently cost a little, recovered as he plays again.' : 'He has not missed matches recently.' },
  ];
}

let world;
function getWorld() {
  if (world) return world;
  const { clubs, players } = build();
  for (const p of players) {
    p.id = slug(p.name);
    p.rating = p.history[p.history.length - 1].rating;
  }
  const ranked = players.slice().sort((a, b) => b.rating - a.rating);
  ranked.forEach((p, i) => { p.worldRank = i + 1; });
  for (const position of SQUAD.map(([x]) => x)) {
    ranked.filter((p) => p.position === position).forEach((p, i, list) => { p.positionRank = i + 1; p.positionOf = list.length; });
  }
  for (const c of clubs) c.squad.slice().sort((a, b) => b.rating - a.rating).forEach((p, i) => { p.clubRank = i + 1; });
  const clubRanked = clubs.slice().sort((a, b) => b.rating - a.rating);
  clubRanked.forEach((c, i) => { c.worldRank = i + 1; });
  // rumours: some players are linked with stronger clubs
  for (const p of players) {
    if (R() < 0.16 && p.role !== 'fringe') {
      const better = clubRanked.filter((c) => c !== p.club && c.rating > p.club.rating - 30);
      p.rumours = [...new Set([pick(better), pick(better), pick(clubRanked)])].slice(0, 1 + Math.floor(R() * 3)).map((c) => c.id);
    } else p.rumours = [];
    // simulated market price: follows the rating with a lag and some noise (preview only)
    let price = Math.exp((p.history[0].rating - 1650) / 160);
    p.price = p.history.map((h, i) => {
      const target = Math.exp((h.rating - 1650) / 160) * (1 + Math.max(0, 24 - p.age) * 0.03);
      price += (target - price) * 0.35 + normal(0, 0.03) * price;
      return { date: h.date, price: Math.max(0.05, Math.round(price * 100) / 100) };
    });
  }
  world = { clubs, players, ranked, clubRanked, asOf: players[0].history[players[0].history.length - 1].date };
  return world;
}

const clubRef = (c) => ({ id: c.id, name: c.name, rating: Math.round(c.rating), league: { id: c.league.id, name: c.league.name } });

export function player(id) {
  const w = getWorld();
  const p = w.players.find((x) => x.id === id);
  if (!p) return null;
  const i = p.worldRank - 1;
  const h = p.history;
  return {
    id: p.id, name: p.name, shortName: p.name.split(' ').slice(1).join(' '), mock: true,
    club: clubRef(p.club), position: p.position, age: p.age, nation: p.nation,
    rating: p.rating, asOf: w.asOf, formula: 'OpenElo beta 0.1',
    rank: { world: p.worldRank, worldOf: w.players.length, position: p.positionRank, positionOf: p.positionOf, club: p.clubRank, clubOf: p.club.squad.length },
    change: { lastMatch: p.matches[p.matches.length - 1].change, season: h[h.length - 1].rating - h[0].rating + p.matches[0].change },
    parts: p.parts, history: h, matches: p.matches, moments: p.moments.slice(-4),
    neighbours: w.ranked.slice(Math.max(0, i - 3), i + 4).map((n) => ({ rank: n.worldRank, id: n.id, name: n.name, club: n.club.name, rating: n.rating })),
    rumours: p.rumours, price: p.price,
  };
}

export function club(id) {
  const w = getWorld();
  const c = w.clubs.find((x) => x.id === id);
  if (!c) return null;
  const table = w.clubs.filter((x) => x.league === c.league).sort((a, b) => b.points - a.points || b.gd - a.gd);
  return {
    ...clubRef(c), mock: true, asOf: w.asOf,
    rank: { world: c.worldRank, worldOf: w.clubs.length, league: w.clubs.filter((x) => x.league === c.league && x.rating > c.rating).length + 1, leagueOf: table.length,
      table: table.indexOf(c) + 1, points: c.points },
    change: { lastMatch: c.matches[c.matches.length - 1].change, season: Math.round(c.rating) - c.history[0].rating + c.matches[0].change },
    history: c.history, matches: c.matches,
    squad: c.squad.map((p) => ({ id: p.id, name: p.name, position: p.position, age: p.age, rating: p.rating, gap: p.rating - Math.round(c.rating),
      parts: p.parts.map(({ key, value }) => ({ key, value })), starts: p.window.slice(-22).filter((s) => s === 1).length,
      lastMatch: p.matches[p.matches.length - 1].change })).sort((a, b) => b.rating - a.rating),
  };
}

export function rankings() {
  const w = getWorld();
  return { asOf: w.asOf, mock: true, players: w.ranked.map((p) => ({ rank: p.worldRank, id: p.id, name: p.name, club: p.club.name, clubId: p.club.id,
    league: p.club.league.name, leagueId: p.club.league.id, position: p.position, age: p.age, nation: p.nation, rating: p.rating,
    week: p.matches[p.matches.length - 1].change, season: p.history[p.history.length - 1].rating - p.history[0].rating + p.matches[0].change })) };
}

export function clubs() {
  const w = getWorld();
  return w.clubRanked.map((c) => ({ ...clubRef(c), rank: c.worldRank, week: c.matches[c.matches.length - 1].change, points: c.points }));
}

export function leagues() {
  const w = getWorld();
  return { asOf: w.asOf, mock: true, leagues: LEAGUES.map((l) => {
    const list = w.clubs.filter((c) => c.league === l);
    const byPoints = list.slice().sort((a, b) => b.points - a.points || b.gd - a.gd);
    return { id: l.id, name: l.name, country: l.country, rating: Math.round(avg(list.map((c) => c.rating))),
      clubs: list.slice().sort((a, b) => b.rating - a.rating).map((c) => ({ id: c.id, name: c.name, rating: Math.round(c.rating),
        week: c.matches[c.matches.length - 1].change, table: byPoints.indexOf(c) + 1, points: c.points, gd: c.gd })) };
  }).sort((a, b) => b.rating - a.rating) };
}

export function week() {
  const w = getWorld();
  const last = (p) => p.matches[p.matches.length - 1];
  const played = w.players.filter((p) => last(p).listed);
  const byChange = played.slice().sort((a, b) => last(b).change - last(a).change);
  const row = (p) => ({ id: p.id, name: p.name, club: p.club.name, clubId: p.club.id, rating: p.rating, change: last(p).change, note: matchLine(p) });
  const clubMoves = w.clubs.slice().sort((a, b) => Math.abs(b.matches.at(-1).change) - Math.abs(a.matches.at(-1).change));
  const star = byChange[0];
  return {
    asOf: w.asOf, mock: true, matchday: w.players[0].matches.length,
    risers: byChange.slice(0, 8).map(row), fallers: byChange.slice(-8).reverse().map(row),
    top: w.ranked.slice(0, 10).map(row),
    clubs: clubMoves.slice(0, 6).map((c) => ({ id: c.id, name: c.name, rating: Math.round(c.rating), change: c.matches.at(-1).change,
      note: `${c.matches.at(-1).goalsFor}–${c.matches.at(-1).goalsAgainst} ${c.matches.at(-1).home ? 'vs' : 'at'} ${c.matches.at(-1).opponent}` })),
    story: { playerId: star.id, title: `${star.name} climbs ${last(star).change} in one match`,
      text: `${matchLine(star)}. He is now rated ${star.rating}, #${star.worldRank} in the world, ${star.rating - Math.round(star.club.rating) >= 0 ? `${star.rating - Math.round(star.club.rating)} above` : `${Math.round(star.club.rating) - star.rating} below`} ${star.club.name}.` },
  };
}

function matchLine(p) {
  const m = p.matches[p.matches.length - 1];
  const result = `${m.goalsFor}–${m.goalsAgainst} ${m.home ? 'vs' : 'at'} ${m.opponent}`;
  return m.note && m.note !== 'Out injured' ? `${m.note} in the ${result}` : `${m.started ? 'Started' : 'Played'} the ${result}`;
}

export function search(query, limit = 8) {
  const q = slug(query);
  if (!q) return [];
  const w = getWorld();
  const players = w.ranked.filter((p) => p.id.includes(q)).slice(0, limit).map((p) => ({ kind: 'player', id: p.id, name: p.name, detail: p.club.name, rating: p.rating }));
  const clubs_ = w.clubRanked.filter((c) => c.id.includes(q)).slice(0, 4).map((c) => ({ kind: 'club', id: c.id, name: c.name, detail: c.league.name, rating: Math.round(c.rating) }));
  return [...clubs_, ...players].slice(0, limit);
}

/* ---------- the market (play money preview) ----------
   A mock of the money model in ADR-0019: one pool for the whole market, a fixed share of it paid out
   each day, split by Elo weight 10^(rating/400) over every share held. Prices come from the simulated
   price series; the order book and fees are illustrative (placeholder fees from the pricing module). */
export const FEES = { taker: 0.05, mint: 0.10 };
export const POOL = { balance: 182000, drain: 0.0035, inflowDay: 640 };   // credits; share paid per day; fees and new-share money per day
const seeded = (id) => makeRandom([...id].reduce((h, c) => (h * 31 + c.charCodeAt(0)) | 0, 7));
const round2 = (v) => Math.round(v * 100) / 100;
const weightOf = (rating) => 10 ** ((rating - 2000) / 400);

let heldCache = null;
function held() {   // how many shares fans hold in each player, and the total Elo weight held
  if (heldCache) return heldCache;
  const w = getWorld();
  const shares = new Map();
  let total = 0;
  for (const p of w.players) {
    const r = seeded(`${p.id}-held`);
    const n = Math.round((15 + r() * 300) * 10 ** ((p.rating - 1800) / 500));
    shares.set(p.id, n);
    total += n * weightOf(p.rating);
  }
  heldCache = { shares, totalWeight: total };
  return heldCache;
}
const dailyPayout = () => POOL.balance * POOL.drain;
export const payoutPerShare = (rating, extraWeight = 0) => round2(dailyPayout() * weightOf(rating) / (held().totalWeight + extraWeight) * 100) / 100;

function marketOf(p) {
  const prices = p.price.map((x) => x.price);
  const price = prices[prices.length - 1];
  const r = seeded(p.id);
  const h = held().shares.get(p.id);
  return { price, week: round2(price - prices[Math.max(0, prices.length - 2)]), season: round2(price - prices[0]),
    newShare: round2(price * (1.06 + r() * 0.06)), payoutDay: payoutPerShare(p.rating), heldShares: h, holders: Math.max(3, Math.round(h / (4 + r() * 8))),
    spark: prices.slice(-12), weight: weightOf(p.rating) };
}

export function market() {
  const w = getWorld();
  return { asOf: w.asOf, mock: true, players: w.ranked.map((p) => ({ id: p.id, name: p.name, club: p.club.name, clubId: p.club.id,
    league: p.club.league.name, position: p.position, rating: p.rating, ...marketOf(p) })) };
}

/* The pool and the next payout. `extraWeight` is the reader's own holdings' weight, added to everyone's. */
export function pool(extraWeight = 0) {
  const now = new Date();
  const next = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1);
  return { ...POOL, payoutToday: round2(dailyPayout()), totalWeight: held().totalWeight + extraWeight, nextPayoutAt: next, mock: true };
}

/* If ratings stay as they are: each position's next payout. The range is what one typical match
   (about ±14 rating points) would do to it. */
export function projection(positions) {
  const w = getWorld();
  const rows = Object.entries(positions).filter(([, x]) => x.shares > 0).map(([id, x]) => ({ p: w.players.find((q) => q.id === id), ...x })).filter((x) => x.p);
  const mine = rows.reduce((s, x) => s + x.shares * weightOf(x.p.rating), 0);
  const total = held().totalWeight + mine;
  const per = (rating) => dailyPayout() * weightOf(rating) / total;
  const out = rows.map((x) => ({ id: x.p.id, name: x.p.name, club: x.p.club.name, position: x.p.position, rating: x.p.rating, shares: x.shares,
    next: round2(x.shares * per(x.p.rating)), low: round2(x.shares * per(x.p.rating - 14)), high: round2(x.shares * per(x.p.rating + 14)),
    weightShare: x.shares * weightOf(x.p.rating) / total }));
  return { rows: out, next: round2(out.reduce((s, r) => s + r.next, 0)), low: round2(out.reduce((s, r) => s + r.low, 0)), high: round2(out.reduce((s, r) => s + r.high, 0)),
    weightShare: mine / total, myWeight: mine };
}

export function book(id) {
  const w = getWorld();
  const p = w.players.find((x) => x.id === id);
  if (!p) return null;
  const m = marketOf(p);
  const r = seeded(`${id}-book`);
  const tick = m.price < 2 ? 0.01 : 0.02;
  const asks = [], bids = [];
  for (let k = 1; k <= 8; k++) {
    const a = round2(m.price + tick * k * (1 + Math.floor(r() * 2)));
    if (a < m.newShare) asks.push({ price: a, shares: Math.round(4 + r() * 60) });
    bids.push({ price: round2(Math.max(0.01, m.price - tick * k * (1 + Math.floor(r() * 2)))), shares: Math.round(4 + r() * 60) });
  }
  return { ...m, asks: dedupe(asks).sort((a, b) => a.price - b.price), bids: dedupe(bids).sort((a, b) => b.price - a.price) };
}
const dedupe = (levels) => [...levels.reduce((map, l) => map.set(l.price, (map.get(l.price) || 0) + l.shares), new Map())].map(([price, shares]) => ({ price, shares }));

/* What a buy of `credits` or a sale of `shares` would do right now: cheapest sellers first, then new
   shares at the new-share price (which rises a little with each share); sales go to the highest buyers. */
export function quote(id, side, amount) {
  const b = book(id);
  if (!b || !(amount > 0)) return null;
  const fills = [];
  if (side === 'buy') {
    let left = amount, shares = 0, fees = 0;
    for (const a of b.asks) {
      const each = a.price * (1 + FEES.taker);
      const n = Math.min(a.shares, Math.floor(left / each));
      if (n <= 0) break;
      fills.push({ from: 'fans', shares: n, price: a.price });
      shares += n; left -= n * each; fees += n * a.price * FEES.taker;
    }
    let mintPrice = b.newShare, minted = 0;
    while (left >= mintPrice * (1 + FEES.mint) && minted < 10000) {
      left -= mintPrice * (1 + FEES.mint); fees += mintPrice * FEES.mint; minted += 1; mintPrice = round2(mintPrice * 1.002);
    }
    if (minted) fills.push({ from: 'new', shares: minted, price: round2((b.newShare + mintPrice) / 2) });
    shares += minted;
    const spent = round2(amount - left);
    return { side, shares, spent, fees: round2(fees), average: shares ? round2(spent / shares) : 0, fills, payoutDay: round2(shares * b.payoutDay) };
  }
  let left = Math.floor(amount), got = 0, fees = 0, sold = 0;
  for (const bid of b.bids) {
    const n = Math.min(bid.shares, left);
    if (n <= 0) break;
    fills.push({ from: 'fans', shares: n, price: bid.price });
    got += n * bid.price * (1 - FEES.taker); fees += n * bid.price * FEES.taker; left -= n; sold += n;
  }
  return { side, shares: sold, unsold: left, received: round2(got), fees: round2(fees), average: sold ? round2(got / sold) : 0, fills, payoutDay: round2(sold * b.payoutDay) };
}
