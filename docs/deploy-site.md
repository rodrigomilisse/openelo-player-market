# Deploying the public site

Written from `frontend/web/site/CONNECT.md` and the guarded build in `frontend/web/build/` (read its `README.md`).
Anything marked **(unverified)** depends on `pipeline/`, which is not on any pushed branch yet.

The site is static files. Three things to know first:

1. **Never publish `frontend/web/site/` directly.** Use the build: it copies `design/stadium.js` next to the site (the 3D scene
   imports `../design/stadium.js`), writes the per-player pages and the sitemap, and enforces the rule that **mock data is never
   indexable or published**. The raw folder is itself safe by default (every page `noindex`, `robots.txt` blocks all), but it
   shows fictional players.
2. **Three.js loads from the jsDelivr CDN** (import map in each page), so there is nothing to install.
3. **Real ratings are not in git.** `site/data/` is gitignored; the daily job writes it.

## 0. Before real numbers go public

- Settle the data licence (ADR-0017, open point 1) and the API-Football plan. The site publishes per-match minutes, goals and
  assists for every player.
- Check the top 50 of the real ratings by eye, and backtest past seasons.
- Make the approval file yourself, by hand (an agent is not allowed to):

  ```bash
  echo '{ "approvedBy": "Your Name", "date": "2026-12-01" }' > frontend/web/.publish-approved
  ```

  Without it, `--production` refuses to build. It is gitignored.

## 1. Try it locally (preview)

```bash
node frontend/web/build/build.mjs          # works with no data: builds from a mock fixture, everything noindex
cd frontend/web/dist && python3 -m http.server 8000   # open http://localhost:8000/
node --test frontend/web/build/guard.test.mjs         # the guarantees as tests (about 45 s)
```

A preview is `noindex` on every page and `robots.txt` blocks all crawlers, whatever data it was built from.

## 2. Host it (Cloudflare Pages, recommended)

```bash
npm install -g wrangler
wrangler login
wrangler pages project create openelo --production-branch main
frontend/web/build/deploy.sh preview       # tests, build, verify, upload as a noindex preview
```

`deploy.sh` is the only supported path: it runs the guard tests, builds, verifies the built folder, then uploads.
Pages serves `404.html` for unknown URLs, and serves `/about` for `about.html` (the build's canonicals and sitemap assume this;
use `--no-pretty-urls` if your host keeps `.html`).

Netlify instead: build with `build.mjs`, then `netlify deploy --prod --dir frontend/web/dist` (skip `deploy.sh`, so run
`node build/verify.mjs dist` yourself first).

## 3. Domain, then settings in `config.js`

1. Register a domain (about €10 a year). Cloudflare dashboard, Workers & Pages, `openelo`, Custom domains, add it.
2. Settings in `frontend/web/site/config.js` (leave `production` and `staticPages` alone; the build writes them):

| Setting | What to do |
|---|---|
| `waitlistUrl` | A form (Formspree, Buttondown, Supabase function) that accepts POST JSON `{ email, country, page }`. |
| `contactEmail` | Cloudflare Email Routing: forward `hello@your-domain` to your inbox. |
| `analytics.plausibleDomain` | Add the site in Plausible with your domain, put the same domain here. |

## 4. Real data and the daily job (unverified)

`pipeline/export.py` must write `data/meta.json` with `"source": "real"`, `asOf` and `generatedAt`
(see `frontend/web/build/README.md`). Without `source: "real"` every page stays noindex.

```
fetch.py (APIFOOTBALL_KEY) -> normalize.py -> rate.py -> export.py --out frontend/web/site/data
```

Then, as `daily.sh` on the machine that runs it:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /path/to/openelo-player-market
export APIFOOTBALL_KEY=...                      # keep it out of git
# 1. fetch, normalize, rate, export into frontend/web/site/data   (exact commands: see pipeline/, not yet pushed)
# 2. test, build with the production gate, verify, upload
frontend/web/build/deploy.sh production https://your-domain
```

```
0 6 * * *  /path/to/daily.sh >> /var/log/openelo-daily.log 2>&1
```

Keep `frontend/web/.build-state.json` and `site/data/weeks/` between runs: the first keeps honest `lastmod` dates in the sitemap,
the second keeps past weeks as permanent pages. `robots.txt` and the sitemap are written by the production build itself.

## 5. Check it after each deploy

- Home page loads, the scene animates, no red errors in the browser console.
- A player page opens by URL; a made-up URL shows the 404 page.
- View source of a player page: the title has his name and rating, there is a canonical link, a robots tag saying `index, follow`.
- `https://your-domain/robots.txt` names the sitemap; `/sitemap.xml` loads; the Search Console sitemap report accepts it.
- A waitlist signup appears in the form service, and a pageview appears in Plausible.
- A preview URL (`preview.openelo.pages.dev`) view source says `noindex, nofollow`.

## Known gaps

- Compare pages are noindex; link previews for arbitrary pairs would need a small Worker. Every page shares one preview image
  (`og.png`); per-player images are a later step.
- Privacy and Terms stay noindex and say "Draft" until you fill in "Who we are" in `privacy.html` and have both reviewed.
- Age and nationality are blank on real data until the `/players` endpoint is added to the pipeline.
