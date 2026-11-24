# Building and publishing the site

**The rule: mock data is never indexable and never published.** Everything here exists to make that hard to break.

```bash
node frontend/web/build/build.mjs                  # PREVIEW into frontend/web/dist (works with no data: uses a mock fixture)
node --test frontend/web/build/guard.test.mjs      # the guarantees below, as tests (about 45 s)
node frontend/web/build/verify.mjs frontend/web/dist
frontend/web/build/deploy.sh preview               # test, build, verify, upload a noindex preview
frontend/web/build/deploy.sh production https://your-domain
```

## The layers (each one holds on its own)

1. **Committed pages are closed.** Every `site/*.html` says `noindex, nofollow`; `site/robots.txt` is `Disallow: /`;
   `site/_headers` sends `X-Robots-Tag: noindex, nofollow`. Deploying the raw `site/` folder, or pointing a host at the repo,
   publishes a site no search engine will index.
2. **At run time.** `site.js` re-asserts `noindex` whenever the page is showing mock data. `api.js` treats data as real only if
   `data/meta.json` says `"source": "real"`. A production build (`config.js` `production: true`) refuses to fall back to
   the mock world at all.
3. **A preview can't be indexable.** `build.mjs` forces `noindex, nofollow` on every page of a preview, writes a blocking
   `robots.txt`, no sitemap, no canonical links. Passing a site URL or approval file to a preview changes nothing.
4. **Production is gated** (`gate.mjs`). `--production` refuses unless all of these hold:
   - `data/meta.json` has `source: "real"`, an `asOf` date and `generatedAt`, no `mock` flag;
   - no JSON file in `data/` contains `"mock": true`, and no player id in `rankings.json` is an id of the fictional mock world;
   - at least 200 players and 20 clubs;
   - the **owner's approval file** `frontend/web/.publish-approved` exists (JSON: `approvedBy`, `date`). Only the owner creates it,
     by hand, once the data licence is settled and the real ratings have been checked (docs/adr/0017, open point 1);
   - `--site-url` is a bare `https://` origin that is not localhost, `*.pages.dev`, `*.netlify.app`, `example.*` and so on.
5. **A policy list decides what ranks** (`policy.mjs`). Only `index`, `how`, `leagues`, `about`, and the generated
   `player-*`, `club-*`, `rankings-*-N`, `week-*` pages can ever be indexable. Market, compare, the query-string pages,
   `rankings.html`, 404, privacy and terms are always noindex. Adding a pattern to `INDEXABLE` is a decision to publish those pages.
6. **The output is verified independently** (`verify.mjs`), by the build, by `deploy.sh`, and by the tests: robots tags, canonicals,
   sitemap contents, `robots.txt`, `_headers`, `config.js`, no `.md` files, and the built `dist/data` is re-checked for mock content.
7. **The tests break loudly.** `guard.test.mjs` covers every refusal above and tampered output. Loosening a test is not a fix.

## What gets generated

For every player and club in the data: `player-<id>.html` and `club-<id>.html` (the site's own templates with the facts in the HTML
plus a visible summary section; the page scripts still draw the charts). Players with fewer than `--min-appearances` (default 10) in
`--window-days` (default 730) get a page but it is `noindex, follow` and is not in any list or sitemap. Also: paginated lists
`rankings-world-1.html`, `rankings-<league>-1.html`, `rankings-<position>-1.html` (100 per page, indexable players only), a
`week-<date>.html` page per matchday from `data/week.json` and `data/weeks/*.json`, summaries on `index.html` and `leagues.html`,
and (production) `sitemap.xml` plus one sitemap per type, with `lastmod` kept only where a page's content changed
(state in `frontend/web/.build-state.json`; keep that file between daily runs).

`--max-files` (default 18,000) stops a build that would outgrow the host's file limit (Cloudflare Pages free: 20,000, verify).
`--no-pretty-urls` if the host keeps `.html` in URLs (Cloudflare Pages and Netlify serve `/about` for `about.html`, which is what
canonicals and the sitemap assume by default).

## The contract with the exporter (`pipeline/export.py`)

`data/meta.json` must contain `"source": "real"`, `asOf`, `generatedAt`. Without `source: "real"` the site treats the data as
mock and every page stays noindex, which is the safe failure. To keep past weeks as permanent pages, also write
`data/weeks/<asOf>.json` (same shape as `week.json`) and do not delete old ones.
