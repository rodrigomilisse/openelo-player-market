# Deploying the public site

Written from `frontend/web/site/CONNECT.md` and the site's code on the `frontend-web` branch.
Anything marked **(unverified)** depends on `pipeline/`, which is not on any pushed branch yet.

The site is static files. There is no server and no build tool. Three things to know first:

1. **Publish a folder that contains `design/stadium.js` too.** `site/scene.js` imports
   `../design/stadium.js`, which lives outside `frontend/web/site/`. Publishing only the `site/` folder
   breaks the 3D scene. The build step below copies that one file next to the site.
2. **Three.js loads from the jsDelivr CDN** (import map in each page), so there is nothing to install.
3. **Real ratings are not in git.** The pages read `data/*.json` when it exists and fall back to the
   mock world when it does not. The daily job writes `data/`, so it should also be the thing that deploys.

## 0. Before real numbers go public

- Settle the data licence (ADR-0017, open point 1) and the API-Football plan. The site publishes
  per-match minutes, goals and assists for every player.
- Check the top 50 of the real ratings by eye, and backtest past seasons.

Deploying the mock world as a "coming soon" site with the waitlist is fine before either.

## 1. Build the publish folder

From the repository root, on the branch that holds the site:

```bash
rm -rf dist && mkdir -p dist/design
cp -R frontend/web/site/. dist/
cp frontend/web/design/stadium.js dist/design/
```

Preview it locally:

```bash
cd dist && python3 -m http.server 8000   # open http://localhost:8000/
```

## 2. Host it (Cloudflare Pages, recommended)

Direct upload, because the daily job produces `data/` and git does not hold it.

```bash
npm install -g wrangler
wrangler login
wrangler pages project create openelo --production-branch main
wrangler pages deploy dist --project-name openelo
```

You get `https://openelo.pages.dev`. `404.html` is served for unknown URLs automatically. The pages are
plain `.html` files, so no rewrite rules are needed.

Netlify instead: `npm install -g netlify-cli && netlify deploy --prod --dir dist`.

## 3. Domain

1. Register a domain (about €10 a year); Cloudflare Registrar or any registrar.
2. Cloudflare dashboard, Workers & Pages, `openelo`, Custom domains, add it. If the domain's DNS is on
   Cloudflare this is one click; otherwise point the nameservers at Cloudflare first.
3. Edit `frontend/web/site/config.js` and set `siteUrl: 'https://your-domain'`, then rebuild and redeploy.

## 4. Waitlist, contact email, analytics (all in `config.js`)

| Setting | What to do |
|---|---|
| `waitlistUrl` | Create a form at Formspree (or Buttondown, or a Supabase function) that accepts POST JSON `{ email, country, page }`. Paste its endpoint URL. Check one test signup lands in your inbox. |
| `contactEmail` | Cloudflare dashboard, Email, Email Routing: forward `hello@your-domain` to your own inbox. Put that address in the setting. |
| `analytics.plausibleDomain` | Add the site in Plausible with your domain, then put the same domain here. Cookie-free, so no consent banner for analytics. |

Rebuild and redeploy after editing `config.js`.

## 5. Real data and the daily job (unverified)

`CONNECT.md` names this chain, run from `pipeline/`:

```
fetch.py        (needs APIFOOTBALL_KEY)  ->  normalize.py  ->  rate.py  ->
export.py --out dist/data --site-url https://your-domain
```

Then deploy. As a script on the machine that runs it, for example `daily.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /path/to/openelo-player-market
export APIFOOTBALL_KEY=...                      # keep it out of git
# 1. rate (exact commands: see pipeline/, not yet pushed)
# 2. build the folder and write data/ into it
rm -rf dist && mkdir -p dist/design
cp -R frontend/web/site/. dist/
cp frontend/web/design/stadium.js dist/design/
# python3 pipeline/export.py --out dist/data --site-url https://your-domain
# 3. publish
wrangler pages deploy dist --project-name openelo
```

Schedule it once a day, after the last matches finish (for example 06:00 UTC):

```
0 6 * * *  /path/to/daily.sh >> /var/log/openelo-daily.log 2>&1
```

`export.py --site-url` also writes `dist/sitemap.xml`. Then uncomment and fill the `Sitemap:` line in
`frontend/web/site/robots.txt`, rebuild and redeploy.

## 6. Check it after each deploy

- Home page loads, the scene animates, no red errors in the browser console.
- Open a player page directly by URL, then reload it.
- A made-up URL shows the 404 page.
- A waitlist signup appears in the form service, and a pageview appears in Plausible.
- Without `data/` the pages say the data is mock. With it, they should not.
- Link preview: paste the URL into a chat app. Every page currently shares one generic image
  (`og.png`) and one title per page type.

## Known gaps this does not fix

- Player and club pages are built in the browser, so search engines and link previews see an empty
  page. Fixing it needs a build step that writes one HTML file per player and club.
- Privacy and Terms still say "Draft" until you fill in "Who we are" in `privacy.html` and have both
  reviewed.
- Age and nationality are blank on real data until the `/players` endpoint is added to the pipeline.
