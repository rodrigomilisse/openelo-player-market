# Public site: player pages

The public OpenElo site: a player's rating, how it is made, and how it moved. No
trading here; the market's design prototypes are in `../design/`, and this page borrows
their night-stadium language (and `../design/stadium.js` for the 3D scene).

```sh
cd frontend/web
python3 -m http.server 8000   # then open http://localhost:8000/site/player.html
```

`player.html?id=<player-id>` loads `data/players/<player-id>.json`. Today there is one
fictional sample player (`tiago-mendonca`, the same fictional world as the prototypes);
the page labels it as a sample.

## The page

- **The equation** is the one bold element: club rating + what he adds = OpenElo, each
  part tappable for a plain-language explanation. It assembles once on load (skipped
  with reduced motion).
- **Behind the hero**, the 3D scene: his rating as a gold ribbon and his club's as a
  silver one, seen from today looking back at August, so the season climbs towards the
  viewer. The ribbons fade once the reader scrolls on.
- **Season chart**: his rating against his club's, the gap shaded, moments pinned;
  pointing reads out any matchday.
- **What moved him**: matches with minutes and rating change (blue up, orange down).
- **Anyone can check this number**, **Around him in the world rankings**, and the
  **waitlist** (local confirmation only until a waitlist endpoint exists).
- No player photos: image rights are an open question, so the vertical surname is the
  portrait.

## Data contract (the future read API, `GET /players/{id}`)

| Field | Meaning |
|---|---|
| `id`, `name`, `shortName`, `position`, `age`, `nation` | identity |
| `club` | `{ id, name, rating }`, the club's rating at `asOf` |
| `rating`, `asOf`, `formula` | the published rating, its date, the rating version |
| `rank` | `{ world, worldOf, position, positionOf, club, clubOf }` |
| `change` | `{ lastMatch, season }` in rating points |
| `parts` | `[{ key, value, label, explain }]`, keys `club`, `selection`, `goals`, `national`, `absence`; values sum to `rating` |
| `history` | `[{ date, rating, clubRating }]`, one per club match |
| `matches` | `[{ date, opponent, home, goalsFor, goalsAgainst, listed, started, minutes, goals, assists, note?, change, rating, clubRating }]` |
| `moments` | `[{ date, kind, text }]`, pinned on the chart (`date` matches a `history` date) |
| `neighbours` | `[{ rank, id, name, club, rating }]` around him in the world ranking |
| `sample` | true for fictional data |

The parts map onto the player model (`research/player_v2.py`, `Player.published`):
team rating after his last match, minutes bonus, national-team points, goal and assist
points, minus the absence discount. `pipeline/rate.py` (on the development branch)
stores the total today; exporting the parts and this JSON is the next step there.
