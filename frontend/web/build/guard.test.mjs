// The guarantees that keep mock data out of search engines, as tests. Run: node --test frontend/web/build/guard.test.mjs
// If one of these fails, do not "fix" it by loosening the test: read README.md first.
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { build } from './build.mjs';
import { verifyDist } from './verify.mjs';
import { writeFixture } from './mock-fixture.mjs';
import { INDEXABLE } from './policy.mjs';

const WEB = join(dirname(fileURLToPath(import.meta.url)), '..');
const SITE = join(WEB, 'site');
const URL_OK = 'https://ratings.openelo.app';
const tmp = await mkdtemp(join(tmpdir(), 'openelo-guard-'));
test.after(() => rm(tmp, { recursive: true, force: true }));

const fixture = join(tmp, 'fixture');
await writeFixture(fixture);

/* The fixture's shape, but with ids no mock world has and no mock flags: what a real export looks like to the gate. */
async function realLooking(dst) {
  await writeFixture(join(tmp, 'seed'));
  const seed = join(tmp, 'seed');
  const rankings = JSON.parse(await readFile(join(seed, 'rankings.json'), 'utf8'));
  const clubs = JSON.parse(await readFile(join(seed, 'clubs.json'), 'utf8'));
  const ids = [...rankings.players.map((p) => p.id), ...clubs.map((c) => c.id)];
  const rename = (text) => ids.reduce((t, id) => t.replaceAll(`"${id}"`, `"${id}-r"`), text);
  const strip = (v) => { if (v && typeof v === 'object') { delete v.mock; Object.values(v).forEach(strip); } return v; };
  const { mkdir } = await import('node:fs/promises');
  await mkdir(join(dst, 'players'), { recursive: true }); await mkdir(join(dst, 'clubs'), { recursive: true });
  const put = async (name, text) => writeFile(join(dst, name), JSON.stringify(strip(JSON.parse(rename(text)))));
  for (const f of ['rankings.json', 'clubs.json', 'leagues.json', 'week.json']) await put(f, await readFile(join(seed, f), 'utf8'));
  for (const p of rankings.players) await put(`players/${p.id}-r.json`, await readFile(join(seed, 'players', `${p.id}.json`), 'utf8'));
  for (const c of clubs) await put(`clubs/${c.id}-r.json`, await readFile(join(seed, 'clubs', `${c.id}.json`), 'utf8'));
  await writeFile(join(dst, 'meta.json'), JSON.stringify({ source: 'real', asOf: rankings.asOf, generatedAt: '2026-01-14T00:00:00Z' }));
}
const approval = join(tmp, 'approved.json');
await writeFile(approval, JSON.stringify({ approvedBy: 'the owner', date: '2026-01-14' }));
const real = join(tmp, 'real');
await realLooking(real);
const opts = (name, extra = {}) => ({ out: join(tmp, name), state: join(tmp, `${name}.state.json`), approval, ...extra });
const robotsOf = (html) => html.match(/<meta\s+name="robots"\s+content="([^"]*)"/)?.[1];
const htmlFiles = async (dir) => (await readdir(dir)).filter((f) => f.endsWith('.html'));

/* ---------- the committed source is closed by default ---------- */
test('every committed page says noindex, nofollow', async () => {
  for (const f of await htmlFiles(SITE)) assert.equal(robotsOf(await readFile(join(SITE, f), 'utf8')), 'noindex, nofollow', f);
});
test('committed robots.txt blocks everything and allows nothing', async () => {
  const t = await readFile(join(SITE, 'robots.txt'), 'utf8');
  assert.match(t, /^Disallow:\s*\/\s*$/m);
  assert.doesNotMatch(t, /^Allow:/m);
  assert.doesNotMatch(t, /^Sitemap:/m);
});
test('committed _headers sends X-Robots-Tag noindex on everything', async () => {
  assert.match(await readFile(join(SITE, '_headers'), 'utf8'), /\/\*\s*\n\s*X-Robots-Tag:\s*noindex, nofollow/);
});
test('committed config is not production and the mock fallback guard is in api.js', async () => {
  assert.match(await readFile(join(SITE, 'config.js'), 'utf8'), /^\s*production:\s*false\s*,/m);
  const api = await readFile(join(SITE, 'api.js'), 'utf8');
  assert.match(api, /CONFIG\.production && !real\) throw/);
  assert.match(api, /meta\.source === 'real'/);
});
test('no sitemap is committed', async () => {
  assert.deepEqual((await readdir(SITE)).filter((f) => /^sitemap/.test(f)), []);
});

/* ---------- what git tracks ---------- */
test('the guards are tracked by git, and data, the approval file and build output never are', () => {
  const ignored = (p) => spawnSync('git', ['check-ignore', '-q', p], { cwd: WEB }).status === 0;
  const git = spawnSync('git', ['rev-parse', '--is-inside-work-tree'], { cwd: WEB });
  if (git.status !== 0) return;   // not a git checkout (a tarball): nothing to check
  for (const p of ['build/gate.mjs', 'build/policy.mjs', 'build/verify.mjs', 'build/build.mjs', 'build/guard.test.mjs', 'site/robots.txt', 'site/_headers', 'site/config.js']) assert.equal(ignored(p), false, `${p} must not be gitignored`);
  for (const p of ['site/data/meta.json', 'site/data/players/x.json', '.publish-approved', 'dist/index.html', '.build-state.json']) assert.equal(ignored(p), true, `${p} must be gitignored`);
});

/* ---------- a preview can never be indexable ---------- */
test('a preview build is noindex everywhere, blocked, without a sitemap, and verifies', async () => {
  const r = await build(opts('prev', { data: fixture }));
  assert.equal(r.indexable, 0);
  const dir = r.out;
  for (const f of await htmlFiles(dir)) assert.equal(robotsOf(await readFile(join(dir, f), 'utf8')), 'noindex, nofollow', f);
  assert.match(await readFile(join(dir, 'robots.txt'), 'utf8'), /^Disallow:\s*\/\s*$/m);
  assert.deepEqual((await readdir(dir)).filter((f) => /^sitemap/.test(f)), []);
  assert.doesNotMatch(await readFile(join(dir, 'player-' + (await readdir(dir)).find((f) => f.startsWith('player-')).slice(7)), 'utf8'), /rel="canonical"/);
  assert.deepEqual(await verifyDist(dir), []);
});
test('a preview with a production-looking site URL and approval is still a preview', async () => {
  const r = await build(opts('prev2', { data: real, siteUrl: URL_OK }));
  assert.equal(r.indexable, 0);
  assert.equal(r.mode, 'preview');
});
test('a preview does not copy internal docs or the fixture', async () => {
  const files = await readdir(join(tmp, 'prev'));
  assert.deepEqual(files.filter((f) => f.endsWith('.md') || f.startsWith('.')), []);
  assert.ok(!files.includes('data'));
});

/* ---------- production refuses everything that is not real, approved, and on a real domain ---------- */
const refuses = (name, extra, pattern) => test(`production refuses: ${name}`, async () => {
  await assert.rejects(build(opts(`p-${name.replace(/\W+/g, '')}`, { production: true, siteUrl: URL_OK, ...extra })), pattern);
});
refuses('no data at all', { data: join(tmp, 'nothing') }, /no data\/meta\.json/);
refuses('the mock fixture', { data: fixture }, /source "mock"/);
refuses('mock data relabelled as real', { data: await (async () => {
  const d = join(tmp, 'liar'); await writeFixture(d);
  await writeFile(join(d, 'meta.json'), JSON.stringify({ source: 'real', asOf: '2026-01-13', generatedAt: 'x' }));
  return d; })() }, /flagged "mock"|ids of the fictional mock world/);
refuses('no owner approval', { data: real, approval: join(tmp, 'missing.json') }, /no publish approval/);
refuses('an empty approval', { data: real, approval: await (async () => { const f = join(tmp, 'empty.json'); await writeFile(f, '{}'); return f; })() }, /approvedBy/);
refuses('a pages.dev address', { data: real, siteUrl: 'https://openelo.pages.dev' }, /preview or placeholder host/);
refuses('http', { data: real, siteUrl: 'http://ratings.openelo.app' }, /must be https/);
refuses('localhost', { data: real, siteUrl: 'https://localhost' }, /preview or placeholder host/);
refuses('no site URL', { data: real, siteUrl: '' }, /not a URL/);
refuses('a path in the site URL', { data: real, siteUrl: 'https://ratings.openelo.app/site' }, /bare origin/);
test('production refuses real-looking data when one file is flagged mock', async () => {
  const d = join(tmp, 'tainted'); await realLooking(d);
  const f = join(d, 'week.json'); await writeFile(f, JSON.stringify({ ...JSON.parse(await readFile(f, 'utf8')), mock: true }));
  await assert.rejects(build(opts('p-tainted', { production: true, siteUrl: URL_OK, data: d })), /week\.json is flagged "mock"/);
});
test('a refused production build leaves no output behind to deploy', async () => {
  assert.equal((await readdir(tmp)).filter((f) => f.startsWith('p-') && !f.endsWith('.state.json')).length, 0);
});

/* ---------- a legitimate production build, and exactly what it opens ---------- */
let prod;
test('production with real data, approval and a real domain builds and verifies', async () => {
  prod = await build(opts('prod', { production: true, siteUrl: URL_OK, data: real }));
  assert.ok(prod.indexable > 100);
  assert.deepEqual(await verifyDist(prod.out), []);
});
test('only policy-listed pages are indexable; market, compare, query pages, 404 and drafts stay noindex', async () => {
  for (const f of await htmlFiles(prod.out)) {
    const robots = robotsOf(await readFile(join(prod.out, f), 'utf8'));
    if (!/noindex/.test(robots)) assert.ok(INDEXABLE.some((re) => re.test(f)), `${f} is indexable but not in policy`);
  }
  for (const f of ['market.html', 'trade.html', 'portfolio.html', 'dividends.html', 'watchlist.html', 'activity.html', 'compare.html', 'player.html', 'club.html', 'rankings.html', '404.html', 'privacy.html', 'terms.html']) {
    assert.match(robotsOf(await readFile(join(prod.out, f), 'utf8')), /noindex/, f);
  }
  for (const f of ['index.html', 'how.html', 'about.html', 'leagues.html']) assert.equal(robotsOf(await readFile(join(prod.out, f), 'utf8')), 'index, follow', f);
});
test('indexable pages have a canonical URL on the site, structured data, and no mock marker', async () => {
  const html = await readFile(join(prod.out, (await readdir(prod.out)).find((f) => /^player-.*-r\.html$/.test(f))), 'utf8');
  assert.match(html, new RegExp(`<link rel="canonical" href="${URL_OK}/player-`));
  assert.match(html, /application\/ld\+json/);
  assert.doesNotMatch(html, /data-source="mock"/);
  assert.match(html, /data-source="real"/);
});
test('the sitemap lists only indexable pages and names no noindex page', async () => {
  const index = await readFile(join(prod.out, 'sitemap.xml'), 'utf8');
  const locs = [];
  for (const m of index.matchAll(/<loc>([^<]+)<\/loc>/g)) locs.push(...[...(await readFile(join(prod.out, m[1].split('/').pop()), 'utf8')).matchAll(/<loc>([^<]+)<\/loc>/g)].map((x) => x[1]));
  assert.ok(locs.length > 100);
  for (const loc of locs) assert.doesNotMatch(loc, /market|trade|portfolio|dividends|watchlist|activity|compare|404|privacy|terms/);
});
test('production config turns the mock fallback off; robots.txt allows crawling and names the sitemap', async () => {
  assert.match(await readFile(join(prod.out, 'config.js'), 'utf8'), /^\s*production:\s*true\s*,/m);
  const r = await readFile(join(prod.out, 'robots.txt'), 'utf8');
  assert.match(r, new RegExp(`Sitemap: ${URL_OK}/sitemap.xml`));
  assert.doesNotMatch(r, /^Disallow:\s*\/\s*$/m);
  assert.match(await readFile(join(prod.out, '_headers'), 'utf8'), /\/data\/\*\s*\n\s*X-Robots-Tag: noindex/);
});
test('a second production build keeps lastmod for unchanged pages', async () => {
  const stateFile = join(tmp, 'prod.state.json');
  const before = JSON.parse(await readFile(stateFile, 'utf8'));
  await build(opts('prod', { production: true, siteUrl: URL_OK, data: real }));
  assert.deepEqual(JSON.parse(await readFile(stateFile, 'utf8')), before);
});

/* ---------- the verifier catches tampering (the deploy script runs it before uploading) ---------- */
const tamper = (name, make, pattern) => test(`verify rejects: ${name}`, async () => {
  const dir = join(tmp, `t-${name.replace(/\W+/g, '')}`);
  const base = await build(opts(`t-${name.replace(/\W+/g, '')}`, make.production ? { production: true, siteUrl: URL_OK, data: real } : { data: fixture }));
  assert.deepEqual(await verifyDist(base.out), []);
  await make.apply(dir);
  assert.match((await verifyDist(dir)).join('\n'), pattern);
});
const sub = (file, from, to) => async (dir) => writeFile(join(dir, file), (await readFile(join(dir, file), 'utf8')).replace(from, to));
tamper('a preview page made indexable', { apply: sub('index.html', /content="noindex, nofollow"/, 'content="index, follow"') }, /index\.html: preview page is/);
tamper('a preview robots.txt that allows crawling', { apply: sub('robots.txt', 'Disallow: /', 'Allow: /') }, /robots\.txt must be/);
tamper('a preview without the header', { apply: sub('_headers', 'noindex, nofollow', 'all') }, /_headers must set/);
tamper('a preview with a sitemap', { apply: (dir) => writeFile(join(dir, 'sitemap.xml'), '<urlset/>') }, /must not contain a sitemap/);
tamper('a preview whose config says production', { apply: sub('config.js', /^(\s*)production: false,/m, '$1production: true,') }, /says production: true/);
tamper('a production market page made indexable', { production: true, apply: sub('market.html', /content="noindex, nofollow"/, 'content="index, follow"') }, /market\.html: indexable, but policy/);
tamper('a production page without a robots tag', { production: true, apply: sub('how.html', /<meta name="robots"[^>]*>/, '') }, /how\.html: no robots meta tag/);
tamper('a production build with mock flagged data', { production: true, apply: sub('data/rankings.json', '{"asOf"', '{"mock":true,"asOf"') }, /dist\/data: .*mock/);
tamper('a production build whose config allows the mock fallback', { production: true, apply: sub('config.js', /^(\s*)production: true,/m, '$1production: false,') }, /production config\.js must say production: true/);
tamper('a production robots.txt that blocks everything', { production: true, apply: sub('robots.txt', 'Allow: /', 'Disallow: /') }, /still blocks everything/);
tamper('a sitemap naming a noindex page', { production: true, apply: sub('sitemap-pages.xml', '</urlset>', `<url><loc>${URL_OK}/market</loc></url></urlset>`) }, /market is not an indexable page/);
tamper('an internal doc in the output', { production: true, apply: (dir) => writeFile(join(dir, 'FEATURES.md'), 'x') }, /FEATURES\.md must not be published/);
test('verify rejects a folder that is not a build output', async () => {
  assert.match((await verifyDist(tmp)).join('\n'), /not a build output/);
});
