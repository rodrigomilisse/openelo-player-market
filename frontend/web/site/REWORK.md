# Rework: one app, one navigation

Status: built on branch `claude/one-app-navigation` (25 November 2026), one Rankings layout (the tabs layout, *A*; the sentence-style *B* was not built). The scroll-to-next-page tour was also removed, and the first tab stays "This week". Decisions are recorded in
`../design/README.md` ("Design language") and `../../CLAUDE.md` (section 4). This file is the
plan to carry them out.

## Why

The header has an Explore/Market pill that swaps the whole navigation, the mobile tab bar and the
look of the scene. A toggle between two sets of pages makes one app contain two apps, and the mode
lives in a global `mode-market` class on `<body>` that CSS and the scene both react to. Replace it
with one navigation and let each page decide how loud it is.

## The new structure

| Tab | Page | Holds |
|---|---|---|
| This week | `index.html` | The latest matchday: winners and losers, top ten, clubs that moved |
| Rankings | `rankings.html` | Everything browsable (below) |
| Portfolio | `portfolio.html` | Holdings, next payout, **dividends** (payout projection and history), open orders |
| More | sheet on a phone, menu on a desktop | Watchlist, Activity, Compare, How it works, About, theme, waitlist, legal |

Search is in the header on every page (a button that opens the field on a phone).
No Market tab for now. Revisit when the price side has enough to fill a page (movers by price,
new-share pricing against rating, the activity feed). Until then price movers can be a second
list on This week and "price" can be a way to rank.

Screens, not tabs: `leagues.html`, `compare.html`, `watchlist.html`, `activity.html`,
`dividends.html` (until it is folded into Portfolio), `trade.html`, `player.html`, `club.html`.
They are reached from Rankings, a player page, Portfolio or More.

## Rankings becomes the browser

Today's `rankings.html` ranks players by rating. `market.html` ("Browse") adds price, payout per
share, holders and a sparkline. The new Rankings is one page that does both.

- **What you rank:** players, clubs or leagues (text tabs with a sliding underline).
- **How:** OpenElo, last match, season, age, and from Browse: price, rising this week, best payout
  for the price. Columns follow the choice.
- **Filters:** league, club, position, age, plus *Watched only* (this is where the watchlist lives)
  and *I hold* if useful. On a phone they sit in the existing filter panel.
- **State in the URL** (`?by=clubs&sort=season&league=...`) so a view can be linked and survives
  the router's keep-alive.
- A row opens the player, club or league. Trading starts from the player page, as it does now.

Two layers, kept apart: the pre-rendered `rankings-<scope>-N.html` pages stay as the plain,
crawlable, rating-only lists the build already produces. The interactive browser, including
simulated prices, is client-side on top. Query-string pages are already always noindex in
`build/policy.mjs`, and simulated prices must never appear in a pre-rendered page.

## What changes in the code

- `site.js`: delete the mode pill, `MARKET_NAV` and `TABS_MARKET`. One `NAV` (This week, Rankings,
  Portfolio) and one tab bar with a More button; extend `MORE_LINKS`. Check the header CTA, which
  `body.mode-market` hides today.
- `site.css`, `mobile.css`: remove the `mode-switch` and `nav-explore`/`nav-market` rules.
  Replace the `body.mode-market` look (upright `h1`, vignette) with a `quiet` setting on the page
  (a class on `<body>` or `<main>`), set in the page's own HTML. `router.js` already swaps the
  body class per page, so this keeps working without a reload.
- `scene.js`: `STATIONS` stays. Quiet pages keep the directors'-box spot and the dim scene through
  `boxScene()`; nothing refers to a global mode.
- Rankings: merge the Browse columns and sorts into `rankings.html`. `getMarket()` (play-money
  prices) feeds the price columns. `api.js` stays the only data access, and new fields go into the
  data contract in `README.md`.
- Portfolio: bring the dividend projection and payout history in, as in-page text tabs
  (Holdings, Dividends) or sections, whichever reads better once built.
- Repoint every link to `market.html` (`portfolio`, `watchlist`, `dividends`, `about`, `404`,
  and `boxScene`'s default `next`) to Rankings. `dividends.html`, `watchlist.html` and
  `activity.html` stay as screens or fold in; decide when building Portfolio.
- Docs in the same commit as the code: `README.md` (pages), `FEATURES.md` (the "Trading (Trade,
  Browse)" heading), `design/README.md`, `../../CLAUDE.md`.

## A blocker to settle first

`build/guard.test.mjs` names `market.html` (lines 141 and 188) in its list of pages that must
be noindex and in a tamper case. Deleting the page would break that test, and the repo rules
forbid editing the guards to get a build through. Two ways:

1. **Keep `market.html` as a tiny noindex redirect to Rankings.** Old links keep working, the
   guard test passes unchanged. This is the plan unless the owner says otherwise.
2. Delete it and have the owner update the test's page list themselves.

Whatever is built, `node --test frontend/web/build/guard.test.mjs` must pass before any commit
under `frontend/web/`, and none of the noindex tags, `robots.txt`, `_headers` or `config.js`
publish lines change.

## Order of work

1. **Rankings, two layouts side by side** (the owner's habit): *A* tabs for what you rank with sort
   chips and filter selects; *B* a sentence-style picker ("Rank players by OpenElo in ..."). The
   owner picks, the other is removed in its own commit.
2. **One navigation:** tab bar and header, More sheet, remove the mode pill and `mode-market`;
   `quiet` per page.
3. **Portfolio with dividends;** Watchlist as a Rankings filter; link Compare and Leagues from
   Rankings and the player page.
4. **Redirect stub for `market.html`,** repoint links, update docs.
5. **Check:** screenshots of every changed page at 1440×900 and 390×844, both themes, plus
   reduced motion (`frontend/CLAUDE.md` section 6); no horizontal scroll at 390px; guard test.
   Then `code-review` and `simplify`.

## Open questions for the owner

- Settled: the first tab is "This week"; dividends are a tab inside Portfolio; everything else (Leagues,
  Compare, Watchlist, Activity, How it works, About, legal) is in More.
- Still open: a Market tab (see above), and whether the sentence-style Rankings picker (*B*) is worth building.
