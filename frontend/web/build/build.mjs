// Builds the publishable folder (frontend/web/dist) from site/ and the exported data.
//
//   node build/build.mjs                       PREVIEW (default). Every page noindex, robots.txt blocks all, no sitemap.
//   node build/build.mjs --production --site-url https://your-domain
//                                              PRODUCTION. Refuses unless the gate passes (real data, owner approval, real URL).
//
// Read build/README.md before changing anything here: this file decides what search engines may see.
import { rm, mkdir, cp, readFile, writeFile, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, join, resolve, sep, basename } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { assertPublishable } from './gate.mjs';
import { writeFixture } from './mock-fixture.mjs';
import { mayBeIndexed, NOINDEX_ALL, NOINDEX_FOLLOW, INDEX } from './policy.mjs';
import { finalize, urlOf } from './finalize.mjs';
import { playerPage, clubPage, rankingPages, weekPage, withSummary, indexSummary, leaguesSummary, appearances, playerFile, clubFile } from './render.mjs';
import { verifyDist } from './verify.mjs';

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const readJson = async (p) => JSON.parse(await readFile(p, 'utf8'));
const hashOf = (s) => createHash('sha256').update(s).digest('hex').slice(0, 16);
const xml = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');

export async function build(opts = {}) {
  const o = {
    production: false, siteUrl: '', data: join(WEB, 'site', 'data'), out: join(WEB, 'dist'), approval: join(WEB, '.publish-approved'),
    minAppearances: 10, windowDays: 730, maxFiles: 18000, pretty: true, state: join(WEB, '.build-state.json'), log: () => {}, ...opts,
  };
  const siteDir = join(WEB, 'site');
  const out = resolve(o.out);
  // The output folder is deleted first: never let that be the source, a parent of it, or the repository.
  if (out === siteDir || out === WEB || siteDir.startsWith(out + sep) || WEB.startsWith(out + sep) || existsSync(join(out, '.git'))) throw new Error(`refusing to use ${out} as the output folder`);
  const mode = o.production ? 'production' : 'preview';

  // ---- the data, and for production the gate ----
  let dataDir = resolve(o.data), usingFixture = false;
  if (o.production) await assertPublishable({ dataDir, siteUrl: o.siteUrl, approvalFile: o.approval });
  else if (!existsSync(join(dataDir, 'meta.json'))) { dataDir = join(WEB, '.fixture-data'); await writeFixture(dataDir); usingFixture = true; }
  const meta = await readJson(join(dataDir, 'meta.json'));
  const source = meta.source === 'real' && meta.mock !== true ? 'real' : 'mock';
  const siteUrl = o.production ? o.siteUrl.replace(/\/$/, '') : '';
  const asOf = meta.asOf;

  // ---- copy the site ----
  await rm(out, { recursive: true, force: true });
  await mkdir(join(out, 'design'), { recursive: true });
  const skip = new Set(['data', 'robots.txt', '_headers', 'config.js']);
  await cp(siteDir, out, { recursive: true, filter: (src) => { const rel = src.slice(siteDir.length + 1); return !(skip.has(rel) || rel.endsWith('.md') || basename(src).startsWith('.')); } });
  await cp(join(WEB, 'design', 'stadium.js'), join(out, 'design', 'stadium.js'));
  if (source === 'real') await cp(dataDir, join(out, 'data'), { recursive: true });

  // ---- templates and data ----
  const tpl = Object.fromEntries(await Promise.all(['player', 'club', 'about', 'index', 'leagues'].map(async (n) => [n, await readFile(join(siteDir, `${n}.html`), 'utf8')])));
  const rankings = await readJson(join(dataDir, 'rankings.json'));
  const clubsList = await readJson(join(dataDir, 'clubs.json'));
  const leagues = await readJson(join(dataDir, 'leagues.json')).catch(() => null);
  const weeks = new Map();
  const addWeek = (w) => { if (w?.asOf) weeks.set(w.asOf, w); };
  addWeek(await readJson(join(dataDir, 'week.json')).catch(() => null));
  if (existsSync(join(dataDir, 'weeks'))) for (const f of await readdir(join(dataDir, 'weeks'))) if (f.endsWith('.json')) addWeek(await readJson(join(dataDir, 'weeks', f)));

  const pages = new Map();   // file -> { html, jsonld, robots? }
  const ranked = [];
  let missing = 0;
  for (const row of rankings.players) {
    let p;
    try { p = await readJson(join(dataDir, 'players', `${row.id}.json`)); } catch { missing += 1; continue; }
    const eligible = appearances(p, asOf, o.windowDays) >= o.minAppearances;
    const page = playerPage(tpl.player, p, { source });
    pages.set(playerFile(p.id), { ...page, robots: eligible ? INDEX : NOINDEX_FOLLOW });
    if (eligible) ranked.push(row);
  }
  for (const c of clubsList) {
    let club;
    try { club = await readJson(join(dataDir, 'clubs', `${c.id}.json`)); } catch { missing += 1; continue; }
    pages.set(clubFile(club.id), { ...clubPage(tpl.club, club, { source }), robots: INDEX });
  }
  if (missing > Math.ceil(0.01 * (rankings.players.length + clubsList.length))) throw new Error(`${missing} players or clubs in the rankings have no data file`);
  for (const [file, page] of rankingPages(tpl.about, ranked, asOf)) pages.set(file, { ...page, robots: INDEX });
  for (const w of weeks.values()) pages.set(`week-${w.asOf}.html`, { ...weekPage(tpl.about, w), robots: INDEX });

  // existing pages that get a summary of the data
  const latestWeek = [...weeks.values()].sort((a, b) => b.asOf.localeCompare(a.asOf))[0];
  const extra = {};
  if (latestWeek) extra['index.html'] = (h) => withSummary(h, indexSummary(latestWeek));
  if (leagues) extra['leagues.html'] = (h) => withSummary(h, leaguesSummary(leagues));

  // ---- write every page through finalize ----
  const written = new Map();   // file -> { robots, jsonld }
  const putPage = async (file, html, { robots: wanted, jsonld = [] }) => {
    const robots = o.production ? wanted : NOINDEX_ALL;   // the one place a preview is forced to noindex
    const final = finalize(html, { file, mode, robots, siteUrl, pretty: o.pretty, jsonld });
    await writeFile(join(out, file), final);
    written.set(file, { robots, hash: hashOf(final) });
  };
  for (const f of (await readdir(out)).filter((x) => x.endsWith('.html'))) {
    let html = await readFile(join(out, f), 'utf8');
    if (extra[f]) html = extra[f](html);
    await putPage(f, html, { robots: mayBeIndexed(f) ? INDEX : NOINDEX_ALL });
  }
  for (const [file, page] of pages) await putPage(file, page.html, page);
  const total = written.size;
  if (total > o.maxFiles) throw new Error(`${total} generated pages exceed the file budget of ${o.maxFiles}; raise --min-appearances or the budget on purpose`);

  // In a preview every page is noindex, whatever policy says for production.
  if (!o.production) for (const [file] of written) { const h = await readFile(join(out, file), 'utf8'); if (!/content="noindex, nofollow"/.test(h)) throw new Error(`${file}: preview page is not noindex`); }

  // ---- config.js, robots.txt, _headers, sitemaps ----
  let config = await readFile(join(siteDir, 'config.js'), 'utf8');
  const swap = (from, to) => { if (!config.includes(from)) throw new Error(`config.js changed: cannot find "${from}"`); config = config.replace(from, to); };
  swap('production: false,', `production: ${o.production},`);
  swap('staticPages: false,', 'staticPages: true,');
  if (o.production) swap("siteUrl: '',", `siteUrl: '${siteUrl}',`);
  await writeFile(join(out, 'config.js'), config);

  const indexed = [...written].filter(([file, w]) => o.production && /^index\b/.test(w.robots));
  if (o.production) {
    await writeFile(join(out, 'robots.txt'), `User-agent: *\nAllow: /\n\nSitemap: ${siteUrl}/sitemap.xml\n`);
    await writeFile(join(out, '_headers'), '/data/*\n  X-Robots-Tag: noindex\n/design/*\n  X-Robots-Tag: noindex\n');
    const state = existsSync(o.state) ? await readJson(o.state) : {};
    const next = {};
    const groups = { pages: [], players: [], clubs: [], lists: [], weeks: [] };
    for (const [file, w] of indexed) {
      const lastmod = state[file]?.hash === w.hash ? state[file].lastmod : asOf.slice(0, 10);
      next[file] = { hash: w.hash, lastmod };
      const g = file.startsWith('player-') ? 'players' : file.startsWith('club-') ? 'clubs' : file.startsWith('rankings-') ? 'lists' : file.startsWith('week-') ? 'weeks' : 'pages';
      groups[g].push(`<url><loc>${xml(urlOf(file, siteUrl, o.pretty))}</loc><lastmod>${lastmod}</lastmod></url>`);
    }
    const names = [];
    for (const [g, urls] of Object.entries(groups)) {
      if (!urls.length) continue;
      await writeFile(join(out, `sitemap-${g}.xml`), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.join('\n')}\n</urlset>\n`);
      names.push(`sitemap-${g}.xml`);
    }
    await writeFile(join(out, 'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${names.map((n) => `<sitemap><loc>${siteUrl}/${n}</loc></sitemap>`).join('\n')}\n</sitemapindex>\n`);
    await writeFile(o.state, JSON.stringify(next));
  } else {
    await writeFile(join(out, 'robots.txt'), await readFile(join(siteDir, 'robots.txt'), 'utf8'));
    await writeFile(join(out, '_headers'), await readFile(join(siteDir, '_headers'), 'utf8'));
  }

  const approval = o.production ? await readJson(o.approval) : null;
  await writeFile(join(out, 'build-info.json'), JSON.stringify({ mode, source, usingFixture, asOf, builtAt: new Date().toISOString(), siteUrl, prettyUrls: o.pretty, maxFiles: o.maxFiles,
    pages: total, indexable: indexed.length, approvedBy: approval?.approvedBy ?? null }, null, 1));

  const problems = await verifyDist(out);
  if (problems.length) throw new Error(`The build failed its own verification:\n  - ${problems.join('\n  - ')}`);
  return { mode, source, usingFixture, out, pages: total, indexable: indexed.length };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const { values: v } = parseArgs({ options: {
    production: { type: 'boolean' }, 'site-url': { type: 'string' }, data: { type: 'string' }, out: { type: 'string' }, approval: { type: 'string' },
    'min-appearances': { type: 'string' }, 'window-days': { type: 'string' }, 'max-files': { type: 'string' }, 'no-pretty-urls': { type: 'boolean' }, state: { type: 'string' },
  } });
  try {
    const r = await build({
      production: !!v.production, siteUrl: v['site-url'] || '', ...(v.data && { data: v.data }), ...(v.out && { out: v.out }), ...(v.approval && { approval: v.approval }),
      ...(v['min-appearances'] && { minAppearances: +v['min-appearances'] }), ...(v['window-days'] && { windowDays: +v['window-days'] }),
      ...(v['max-files'] && { maxFiles: +v['max-files'] }), pretty: !v['no-pretty-urls'], ...(v.state && { state: v.state }),
    });
    console.log(`${r.mode} build of ${r.source} data${r.usingFixture ? ' (mock fixture)' : ''}: ${r.pages} generated or rewritten pages, ${r.indexable} indexable, in ${r.out}`);
    if (r.mode === 'preview') console.log('Preview output is noindex and robots-blocked by design. It cannot be made indexable without --production.');
  } catch (e) { console.error(e.message); process.exit(1); }
}
