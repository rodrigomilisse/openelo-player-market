# Frontend: read this before building

"This level" means the public OpenElo site and its market preview in `frontend/web/`: a
real-time Three.js night stadium behind liquid-glass UI, aiming at Awwwards WebGL sites
(Igloo Inc, Lusion, Bruno Simon, Immersive Garden) rather than a dashboard. This file says
what to load, what the owner has already decided, and how to check your work. It summarises;
where a linked source says more, the source wins.

The general playbook (skills, stack choice, techniques, the owner's taste, the quality floor,
a starter page and a screenshot script) is the portable skill in
`.claude/skills/immersive-web/`. Load it first. This file adds what is specific to OpenElo.

## 1. Where things live

The frontend is not on `master` yet. If `frontend/web/` is missing from your checkout, run
`git fetch origin frontend-web` and work from that branch. To only read a file, use
`git show origin/frontend-web:<path>`.

| Branch | What it holds |
|---|---|
| `frontend-web` | The site (`frontend/web/site/`), the design prototypes (`frontend/web/design/`), the frontend-design skill (`.claude/skills/frontend-design/`), MCP servers (`.mcp.json`), `docs/adr/0019-web-frontend.md` |
| `claude/modest-faraday-c9h5od` | `pipeline/`: fetch, rate, and `export.py`, which writes the site's `data/*.json` |
| `claude/stoic-darwin-cdxfeg` | `docs/deploy-site.md`: build folder, Cloudflare Pages, domain, daily job |

Two ADRs share the number 0019 (`0019-web-frontend.md` on `frontend-web`,
`0019-dividend-pool-elo-weights-stake-split.md` on `master`). Cite them by file name.

## 2. Load before you start

| Load | Where | When |
|---|---|---|
| **frontend-design skill** | `.claude/skills/frontend-design/SKILL.md` | Any new page, section or visual direction. On `frontend-web` it loads as a project skill; elsewhere read it with `git show`. Follow its process: token plan, review against the brief, build, screenshot critique. |
| **Design language and techniques** | `frontend/web/design/README.md` | Always. "Design language" holds the owner's decisions; "How this level is made" holds the 3D techniques; "References" lists the sites to match. |
| **Site architecture** | `frontend/web/site/README.md` | Always. Pages, the data contract (the future read API), how the living scene works. |
| **Backend assumptions** | `frontend/web/site/FEATURES.md` | Before mocking anything the backend doesn't serve yet. |
| **Outside connections** | `frontend/web/site/CONNECT.md`, `config.js` | Before adding a third-party service. |
| **Product rules** | `docs/Spec.md` (section 3), `docs/adr/0019-web-frontend.md` | Anything touching prices, money or the market. |
| **Earlier design rounds** | https://claude.ai/artifact/JdB17FXjVqRfpnFH8xV7cj | The owner's design canvas: the chosen terminal direction plus an Archive page of the looks rejected. Read it with the Artifact tool. |

Session skills and tools, when your session lists them (skip any it doesn't):

- `dataviz`: before any new chart. Its method applies, but its palette doesn't: use this
  site's tokens (gold rating, blue up, orange down, club grey).
- `run`: to launch the site and take screenshots.
- `code-review`, `simplify`, `security-review`: before you hand work back.
- `anthropic-skills:built-in-browser` or `anthropic-skills:chrome-browser`: to show the
  site on the owner's own machine.
- `artifact-design`: only for a throwaway preview published as an Artifact, never for site code.
- MCP servers in `.mcp.json`: **Playwright** for screenshots and clicking through pages;
  **shadcn** only for the future React client (section 3). The site uses no component library.

## 3. The stack

**Public site and market preview** (`frontend/web/site/`):

- No build step, no framework, no npm dependencies: plain HTML pages and native ES modules.
- Three.js **0.160.0** from jsDelivr through an import map (`three`, `three/addons/`).
  Postprocessing: `EffectComposer` and `UnrealBloomPass`, with bloom on screens wider than 860px only.
- Fonts from Google Fonts: Barlow Condensed and Barlow Semi Condensed.
- Charts are hand-written SVG (`lineChart` in `site.js`), plus particle formations in
  `scene.js`. No chart library.
- Modules:
  - `site.js`: shell, header, search, formatters, `escape`, the chart.
  - `router.js`: page changes without a reload; visited pages stay alive and links prefetch.
  - `scene.js`: the stadium and about 9,000 particles, the page spots (`STATIONS`) and `immersive()`.
  - `api.js`: the only data access. It reads `data/` when present, otherwise `mock.js`.
  - `mock.js`: a seeded fictional world (3 leagues, 36 clubs, 792 players).
  - `market-ui.js`: shared by the Market pages.
  - `config.js`: outside services; empty means not connected.
- Run it from `frontend/web`, not `site/`, because `scene.js` imports `../design/stadium.js`:
  `cd frontend/web && python3 -m http.server 8000`, then open `http://localhost:8000/site/`.

**Design prototypes** (`frontend/web/design/`): references for look and feel, not
production code. The site reuses `stadium.js`. Don't build site features into the prototypes.

**Future logged-in client** (`docs/adr/0019-web-frontend.md`, proposed, not built): React,
TypeScript and Vite; types from OpenAPI (`openapi-typescript`); Mock Service Worker for
mocks; TanStack Query; an `Idempotency-Key` on every write; integer money; a Vite proxy to
`market-service`. Don't start it unless asked. Until then the market preview lives in the site.

**Not built, on the owner's list of next steps**: Lenis smooth scroll, glTF models from
Blender, sound with Web Audio. Add these only when asked. Bloom is already done.

## 4. What the owner has decided

Don't reopen these unless asked.

**Look**

| Token | Dark (night) | Light (overcast day) | Use |
|---|---|---|---|
| `--night` | `#060B14` | `#E6EAF0` | Ground, scene sky and fog |
| `--ink` | `#E4ECF5` | `#0F1B2B` | Text |
| `--muted` | `#93A6BC` | `#526378` | Secondary text |
| `--elo` | `#FFD66B` | `#9A6700` | The rating, and only the rating (plus focus rings and primary actions) |
| `--up` | `#5AA9FF` | `#1B62C2` | Share price, rising |
| `--down` | `#FF9A4D` | `#BF520A` | Falling; dashed orange is the new-share price ceiling |
| `--club` | `#A9BBD0` | `#66798E` | The club's line |
| `--rival` | `#8FD3FF` | `#0B74AD` | The second player on compare |

- **Night stadium.** A live 3D stadium behind every page, with crowd lights, floodlights,
  dust and a pitch grid. Glass panels carry all UI over it.
- **Two lines per player.** The rating moves after a match and the price follows. That is
  the core feeling of the product.
- **Rising blue, falling orange. Never green and red** (colour-blind safe).
- **Themes.** Dark `#060B14` is the original night: a lifted navy was tried and reverted.
  Light is a grey-white overcast day: a darker grey dusk was tried and reverted. The theme follows the
  system until the reader picks one, which is stored in `localStorage` as `openelo-theme`.
  An inline script at the top of `<head>` sets `data-theme` before paint, and the scene
  listens for `themechange`. Every new colour needs a value for both themes.
- **Type.** Barlow Condensed for display (`h1`: 900 italic, uppercase), Barlow Semi
  Condensed for UI, tabular figures everywhere.
- **Photos** are tall vertical panels on the side, never a banner on top: black and white,
  tinted in the page colour, with the surname set vertically in outlined italic capitals
  (the player-page nameplate). The stand-in photo must be replaced before launch: player
  image rights are an open question.
- **One app, no mode switch** (25 Nov 2026, replaces "two modes, one site"). A toggle between
  Explore and Market made one product look like two apps. There is one navigation: tabs
  *This week*, *Rankings*, *Portfolio* (dividends inside it) and *More*, with search always at
  the top. Leagues, Compare, Watchlist, Activity and Browse are screens reached from those
  tabs, not tabs of their own. A *Market* tab is deliberately left out until it has a job
  Rankings and Portfolio don't (the price side: movers by price, new-share pricing,
  activity); revisit then. The loud/quiet contrast stays as a property of the page, not a
  global mode: ratings pages are loud (italic display type, a living scene whose particles
  form the page's data); pages about the reader's money are quiet (the directors' box, a
  dimmed and still scene, upright headings). Plan: `frontend/web/site/REWORK.md`.
- **Interaction.** Fewer buttons, more motion: text tabs with a sliding underline, sliders,
  slide-to-confirm or hold-to-confirm, charts you scrub that drive the headline numbers.
- **Motion.** Real 3D, never video scrubbing. Scroll drives the camera, eased; the pointer
  adds parallax and swipes scatter the particles, which form each page's data. Motion comes
  from the scene, not from fade-in entrances on every section or hover effects on every card.

**Rejected**: the consumer-fintech and sports-editorial looks (on the design canvas's
Archive page); the light neobank-style app design ("the dark one is the keeper"); the grey
dusk light theme; the lifted dark navy; an Explore/Market mode toggle (bad UX: an app
shouldn't contain two apps).

**How the owner likes to work** (from the commit history):

- For a new direction, build two or three runnable alternatives side by side and let the
  owner choose (for example `trade.html`, `trade-hud.html`, `trade-rail.html`). Keep the
  chosen one and remove the others in their own commit.
- Write decisions into the folder's README as they are made.
- Label anything mock, simulated, projected or draft on the page itself. Say in the product,
  not only in the terms, that a nominal price is not a claim on any real transfer (Spec,
  section 3).
- Connect outside services through `config.js` (the site still works when a setting is
  empty) and list them in `CONNECT.md`. List what the backend must provide in `FEATURES.md`.

## 5. Hard rules

- **Money is integer.** Store amounts in minor units (an API amount: 1 credit = 100,000
  units; on screen: whole hundredths of a credit) and format them with integer division and
  remainder, never float arithmetic. `cr()` in `market-ui.js` rounds floats because the
  preview runs on play money. Real-money code follows the ADR.
- **`escape()` every string** that goes into `innerHTML`.
- **`api.js` is the only data access.** Pages never fetch directly. A new field goes into
  the data contract in `site/README.md`.
- **Reduced motion**: still frames and no automatic camera flights. Redraw only on resize or
  a state change.
- **Phones** (860px and narrower): half the particles, no bloom, pixel ratio capped at 1.5,
  one column, no horizontal scroll at 390px.
- **Keyboard and screen readers**: real buttons and links, a visible gold focus ring,
  `aria-pressed` or `aria-checked` on toggles, `aria-hidden` on the canvas and grain.
- **Formatting**: `Intl.NumberFormat('en-GB')`, a real minus sign (−) through `signed()`,
  dates in UTC.
- **Avoid the tells** listed in the frontend-design skill: ALL-CAPS eyebrow labels, meta
  strings joined with middle dots (identity lines here use commas), `→` on links, one
  accented word in a headline, numbered markers on content that isn't a sequence.
- **Copy**: plain, sentence case, from the reader's side. A button names its action, and an
  error says what happened and what to do next. Match the voice of `how.html`. Don't invent
  figures outside the mock world.
- **A new page**: share the shell (`<header data-shell="header">` and `shell()`), put the
  theme script first in `<head>`, copy the meta and Open Graph tags from `index.html`, give
  it a spot in `STATIONS`. If it belongs under a tab, say so in `tabOf()` in `router.js`; if it is about
  the reader's money, give `<body>` the `quiet` class.

## 6. Check your work

1. Serve the site (section 3). In mock mode the console shows one 404 for `data/meta.json`;
   that is expected.
2. Screenshot each changed page at 1440×900 and 390×844, in both themes, and once with
   reduced motion. Check the console for errors.
3. Look at the screenshots yourself and critique them against section 4. Then remove one
   thing that doesn't earn its place.
4. Send the owner the screenshots. Deployment is covered in `docs/deploy-site.md`.

`.claude/skills/immersive-web/scripts/screenshot.cjs` does step 2 in one command. Run it
with `THEME_KEY=openelo-theme` and the base URL `http://localhost:8000/site/`. In mock mode
it reports the expected 404 for `data/meta.json`.

**In a Claude Code cloud session**, the network policy blocks jsDelivr (the proxy answers
`CONNECT` with 403), so the scene can't load Three.js. Google Fonts and npm are allowed.
Chromium and Playwright are already installed: use `require('playwright')` and don't run
`playwright install`. Install Three.js into the scratchpad with
`npm install three@0.160.0`, then serve it in place of the CDN:

```js
// THREE_DIR: the folder where you ran npm install
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
// reducedMotion: 'reduce' in newContext for the reduced-motion pass
await context.addInitScript(() => localStorage.setItem('openelo-theme', 'light'));
await context.route('https://cdn.jsdelivr.net/npm/three@0.160.0/**', (route) => {
  const rel = new URL(route.request().url()).pathname.replace('/npm/three@0.160.0/', '');
  route.fulfill({ path: `${THREE_DIR}/node_modules/three/${rel}`, contentType: 'text/javascript' });
});
```

This was tested on 22 November 2026: launched with
`chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })`, the
scene, bloom, glass and both themes render headless. Wait about 2.5 seconds after
`networkidle` so the particles settle before the screenshot.

## 7. Ship

- Commit messages follow `git log origin/frontend-web`: a subject naming what changed
  ("Site: …", "Player nameplate: …", "Light theme: …") and a body saying what and why.
- Update `README.md`, `FEATURES.md` and `CONNECT.md` in the same commit as the change.
- Keep this file current: when the owner decides something new, add it to section 4 and to
  `frontend/web/design/README.md`.
