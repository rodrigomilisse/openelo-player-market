# Connections to add

The site runs without any of these; each one turns a placeholder into the real thing.
Settings live in `config.js` unless noted.

| # | Connection | Unlocks | What to do | Cost |
|---|---|---|---|---|
| 1 | **Domain + static host** (Cloudflare Pages or Netlify) | The site is live; `404.html` is served for unknown URLs | Point the host at `frontend/web/site/`, add the domain, set `siteUrl` | Free (domain ~€10/yr) |
| 2 | **Waitlist endpoint** (Formspree, Buttondown, or a Supabase function) | Waitlist emails are actually saved | Create a form that accepts POST JSON `{ email, country, page }`, set `waitlistUrl` | Free tier |
| 3 | **Contact email** (e.g. Cloudflare Email Routing to your inbox) | About and Privacy show a real address | Set `contactEmail` | Free |
| 4 | **Analytics** (Plausible) | Page and waitlist counts, cookie-free | Add the site in Plausible, set `analytics.plausibleDomain` | ~€9/mo (Cloudflare Web Analytics is free but needs a small change here) |
| 5 | **API-Football from your own connection** | Real ratings for every league in the plan | `pipeline/fetch.py` with `APIFOOTBALL_KEY`, then `normalize.py`. The export must write `data/meta.json` with `"source": "real"` (without it the site stays mock and noindex). | Free plan (ADR-0017 suggests the Pro plan for line-ups; check) |
| 6 | **Daily job** (cron on your machine, or a small VPS) | Ratings refresh by themselves | `fetch → normalize → rate → export --out <site>/data --site-url <domain>`, then deploy | Free on your machine |
| 7 | **Player details** (API-Football `/players` endpoint) | Age and nationality on every page (blank today) | Extend `fetch.py`/`normalize.py`; uses extra quota | Free plan, quota |
| 8 | **Company details + legal review** | Privacy and Terms lose their "Draft" label | Fill in `privacy.html` "Who we are", review both | Lawyer time |
| 9 | **Market backend** | Real accounts, trades, payouts | Everything in `FEATURES.md` | Later |

After 1 and 6, add the sitemap line to `robots.txt` (`export.py --site-url` writes `sitemap.xml`).

Publish only through `build/deploy.sh` (see `../build/README.md` and `docs/deploy-site.md`): a preview is always noindex; production needs real data, your hand-made approval file `frontend/web/.publish-approved`, and a real https domain.
