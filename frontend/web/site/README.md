# Public site

The public OpenElo site: player and club ratings, how they are made, and how they moved.
No trading here; the market's design prototypes are in `../design/`. The site borrows their
night-stadium language, and `../design/stadium.js` for the player page's 3D scene.

```sh
cd frontend/web
python3 -m http.server 8000   # then open http://localhost:8000/site/
```

## Pages

| Page | What it shows |
|---|---|
| `index.html` | This week: the matchday's headline mover, biggest risers and fallers, the top ten, clubs that moved |
| `rankings.html` | Every player: filter by name, league, club, position and age; sort by rating, last match, season, age |
| `player.html?id=` | The rating as an equation (club + selection + goals and assists + national team − absence), his season against his club's (3D behind the hero, 2D chart), **if he moved** (swap in any club's rating, choose how often he'd play), **market price** (simulated preview), matches, the parts explained, ranking neighbours |
| `club.html?id=` | Club rating and ranks, **who carries the team** (each player's gap above or below the club), the club's season, results |
| `compare.html?a=&b=` | Two players side by side: verdict, part by part, both seasons on one chart |
| `leagues.html` | Leagues by average club rating; each league's clubs by rating against their table position |
| `how.html` | The formula in plain steps, a worked example, how to check it, questions |

Every page shares `site.js` (header with search, mock-data note, waitlist footer, formatters,
the line chart) and `site.css` (tokens and components).

## Data: mock today, real later

`api.js` is the only data access. Today it returns `mock.js`: a seeded, fictional world (3
leagues, 36 clubs, 792 players, one simulated season) generated in the browser, following
the real formula's structure, so each player's parts sum to his rating. Every page says the
data is mock. When the rating service publishes real data, each `api.js` function fetches it
instead; the pages do not change.

Still mock or local even with real ratings, and labelled as such:
- **Market price** is simulated: the market does not exist yet.
- **Leagues**: comparing leagues needs European-competition results in the database.
- **Waitlist** confirms in the browser only, until a waitlist endpoint exists.
- **If he moved** is a projection: the new club's rating replaces his club's; selection is
  his current bonus, or a typical rotation (−110) or bench (−230) bonus.

## Data contract (the future read API)

`getPlayer(id)`, `GET /players/{id}`:

| Field | Meaning |
|---|---|
| `id`, `name`, `shortName`, `position`, `age`, `nation` | identity |
| `club` | `{ id, name, rating, league: { id, name } }`, the club's rating at `asOf` |
| `rating`, `asOf`, `formula` | the published rating, its date, the rating version |
| `rank` | `{ world, worldOf, position, positionOf, club, clubOf }` |
| `change` | `{ lastMatch, season }` in rating points |
| `parts` | `[{ key, value, label, explain }]`, keys `club`, `selection`, `goals`, `national`, `absence`; values sum to `rating` |
| `history` | `[{ date, rating, clubRating }]`, one per club match |
| `matches` | `[{ date, opponent, home, goalsFor, goalsAgainst, listed, started, minutes, goals, assists, note?, change, rating, clubRating }]` |
| `moments` | `[{ date, kind, text }]`, pinned on the chart |
| `neighbours` | `[{ rank, id, name, club, rating }]` around him in the world ranking |
| `rumours` | club ids he is linked with (prefills "if he moved") |
| `price` | `[{ date, price }]`, market price per share; simulated until the market exists |

`getClub(id)`: `{ id, name, rating, league, rank: { world, worldOf, league, leagueOf, table, points }, change, history: [{ date, rating }], matches: [{ date, opponent, opponentId, home, goalsFor, goalsAgainst, change, rating }], squad: [{ id, name, position, age, rating, gap, parts, starts, lastMatch }] }`

`getRankings()`: `{ asOf, players: [{ rank, id, name, club, clubId, league, leagueId, position, age, nation, rating, week, season }] }`

`getClubs()`: `[{ id, name, rating, league, rank, week, points }]`, best first.

`getLeagues()`: `{ asOf, leagues: [{ id, name, country, rating, clubs: [{ id, name, rating, week, table, points, gd }] }] }`

`getWeek()`: `{ asOf, matchday, risers, fallers, top, clubs, story: { playerId, title, text } }`

`search(query)`: `[{ kind: 'player' | 'club', id, name, detail, rating }]`

The parts map onto the player model (`research/player_v2.py`, `Player.published`): team
rating after his last match, minutes bonus, national-team points, goal and assist points,
minus the absence discount. `pipeline/rate.py` (development branch) stores the total today;
exporting the parts and these shapes is the next step there.

## The living scene (`scene.js`)

Behind every page: the night stadium and about 9,000 particles (4,500 on phones).

- **Formations.** Each page passes three shapes (its data) and scroll keyframes; the
  particles morph between them, staggered, swirling while they travel. Keyframes can be a
  scroll fraction or a selector (`'#stage-rating'`: when that element is centred on screen),
  and can set `shift` (0 centres the scene; the default keeps it right of hero text).
- **Stages.** Near-empty `.stage` sections give a formation room to play in the open, with
  one caption line: the player's rating, the club's squad columns, compare's ratings and
  seasons, the matchday's biggest climb.
- **Physics.** Each particle is sprung to its place in the shape. A pointer swipe kicks the
  particles near its path (along the swipe and outward); they drift back over a few seconds.
- **The tour.** Every page has a spot in the stadium (`STATIONS`). Keep scrolling at the
  bottom of a page and the next-stop card's ring fills; the camera flies to the next page's
  spot and opens it there. Order: this week, rankings, leagues, compare, how it works;
  a player leads to his club, a club to its league.
- **Liquid glass.** Panels, the header and controls: a refraction filter (Chromium; a plain
  blur elsewhere), a bright edge, and a highlight that follows the pointer.
- Bloom on larger screens; reduced motion gets still frames and no automatic flights.
