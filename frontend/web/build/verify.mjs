// Checks a BUILT folder, independently of how it was built. The build runs it before it finishes, the deploy script runs it
// again before uploading, and the tests run it on tampered output. Exit code 1 means: do not publish this folder.
import { readFile, readdir, stat } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { pathToFileURL } from 'node:url';
import { mayBeIndexed, robotsOf, NOINDEX_ALL, problemsWithSiteUrl } from './policy.mjs';
import { dataProblems } from './gate.mjs';

async function* walk(dir) {
  for (const e of await readdir(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) yield* walk(p); else yield p;
  }
}
const read = (p) => readFile(p, 'utf8').catch(() => null);
const urlToFile = (loc, siteUrl, pretty) => {
  const path = loc.slice(siteUrl.length).replace(/^\//, '');
  return path === '' ? 'index.html' : pretty ? `${path}.html` : path;
};

export async function verifyDist(dir) {
  const problems = [];
  const infoText = await read(join(dir, 'build-info.json'));
  if (!infoText) return [`${dir} has no build-info.json: not a build output`];
  const info = JSON.parse(infoText);
  const production = info.mode === 'production';
  if (!['preview', 'production'].includes(info.mode)) return [`build-info.json has unknown mode "${info.mode}"`];

  const files = [];
  for await (const f of walk(dir)) files.push(relative(dir, f));
  if (files.length > (info.maxFiles || 18000)) problems.push(`${files.length} files exceeds the ${info.maxFiles || 18000} file budget`);
  for (const f of files) if (/\.md$/.test(f) || f.startsWith('.')) problems.push(`${f} must not be published`);

  const indexed = new Set();
  for (const f of files.filter((x) => x.endsWith('.html'))) {
    const html = await readFile(join(dir, f), 'utf8');
    const robots = robotsOf(html);
    const canonical = /<link\s+rel="canonical"/i.test(html);
    if (!robots) { problems.push(`${f}: no robots meta tag`); continue; }
    const isIndex = !/noindex/i.test(robots);
    if (!production) {
      if (robots !== NOINDEX_ALL) problems.push(`${f}: preview page is "${robots}", must be "${NOINDEX_ALL}"`);
      if (canonical) problems.push(`${f}: preview page has a canonical link`);
    } else if (isIndex) {
      indexed.add(f);
      if (f.includes('/') || !mayBeIndexed(f)) problems.push(`${f}: indexable, but policy.mjs does not allow this page to be indexed`);
      if (!canonical) problems.push(`${f}: indexable page without a canonical link`);
      if (/data-source="mock"/.test(html)) problems.push(`${f}: indexable page built from mock data`);
    } else if (canonical) problems.push(`${f}: noindex page carries a canonical link`);
  }

  const robotsTxt = (await read(join(dir, 'robots.txt'))) || '';
  const headers = (await read(join(dir, '_headers'))) || '';
  const config = (await read(join(dir, 'config.js'))) || '';
  const sitemaps = files.filter((f) => /^sitemap.*\.xml$/.test(f));
  if (!production) {
    if (!/^Disallow:\s*\/\s*$/m.test(robotsTxt) || /^Allow:/m.test(robotsTxt)) problems.push('preview robots.txt must be "Disallow: /" with no Allow');
    if (!/\/\*\s*\n\s*X-Robots-Tag:\s*noindex/.test(headers)) problems.push('preview _headers must set X-Robots-Tag: noindex on /*');
    if (sitemaps.length) problems.push(`preview must not contain a sitemap (${sitemaps.join(', ')})`);
    if (/^\s*production:\s*true\s*,/m.test(config)) problems.push('preview config.js says production: true');
  } else {
    problems.push(...problemsWithSiteUrl(info.siteUrl || ''));
    if (info.source !== 'real') problems.push(`production build from "${info.source}" data`);
    if (!/^\s*production:\s*true\s*,/m.test(config)) problems.push('production config.js must say production: true (it turns the mock fallback off)');
    if (!new RegExp(`^Sitemap:\\s*${(info.siteUrl || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}/sitemap\\.xml\\s*$`, 'm').test(robotsTxt)) problems.push('production robots.txt must name the sitemap');
    if (/^Disallow:\s*\/\s*$/m.test(robotsTxt)) problems.push('production robots.txt still blocks everything');
    if (!/\/data\/\*\s*\n\s*X-Robots-Tag:\s*noindex/.test(headers)) problems.push('production _headers must set X-Robots-Tag: noindex on /data/*');
    if (!sitemaps.includes('sitemap.xml')) problems.push('production build has no sitemap.xml');
    for (const sm of sitemaps.filter((f) => f !== 'sitemap.xml')) {
      const xml = await readFile(join(dir, sm), 'utf8');
      const locs = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
      if (locs.length > 50000) problems.push(`${sm} lists more than 50,000 URLs`);
      for (const loc of locs) {
        if (!loc.startsWith(`${info.siteUrl}/`)) { problems.push(`${sm}: ${loc} is outside ${info.siteUrl}`); continue; }
        const file = urlToFile(loc, info.siteUrl, info.prettyUrls !== false);
        if (!indexed.has(file)) problems.push(`${sm}: ${loc} is not an indexable page of this build`);
      }
    }
    // The artifact is re-checked on its own data, not on what the build says about it.
    problems.push(...(await dataProblems(join(dir, 'data'))).map((p) => `dist/data: ${p}`));
    const s = await stat(join(dir, 'data')).catch(() => null);
    if (!s) problems.push('production build has no data folder');
  }
  return problems;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const dir = process.argv[2] || new URL('../dist', import.meta.url).pathname;
  const problems = await verifyDist(dir);
  if (problems.length) { console.error(`NOT SAFE TO PUBLISH ${dir}:\n  - ${problems.join('\n  - ')}`); process.exit(1); }
  console.log(`verified ${dir}`);
}
