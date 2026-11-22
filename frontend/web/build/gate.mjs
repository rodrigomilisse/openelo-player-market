// The production gate. A production build refuses unless EVERY check here passes; nothing in it is optional.
// It exists so fictional (mock) data can never reach a public, indexable site. See README.md.
import { readFile, readdir, stat } from 'node:fs/promises';
import { join } from 'node:path';
import * as mock from '../site/mock.js';
import { problemsWithSiteUrl } from './policy.mjs';

const MOCK_MARK = /"mock"\s*:\s*true/;

async function* jsonFiles(dir) {
  for (const e of await readdir(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) yield* jsonFiles(p);
    else if (e.name.endsWith('.json')) yield p;
  }
}
const readJson = async (p) => JSON.parse(await readFile(p, 'utf8'));
const exists = (p) => stat(p).then(() => true, () => false);

/* Is this data folder real, published-quality data? Returns a list of problems (empty = fine). Also used on the built dist/data. */
export async function dataProblems(dataDir, { minPlayers = 200, minClubs = 20 } = {}) {
  const problems = [];
  if (!(await exists(join(dataDir, 'meta.json')))) return [`no data/meta.json in ${dataDir}`];
  let meta;
  try { meta = await readJson(join(dataDir, 'meta.json')); } catch (e) { return [`data/meta.json is not valid JSON (${e.message})`]; }
  if (meta.source !== 'real') problems.push(`data/meta.json says source "${meta.source}", not "real" (the exporter must write source: "real")`);
  if (meta.mock === true) problems.push('data/meta.json is flagged mock');
  if (!/^\d{4}-\d{2}-\d{2}/.test(meta.asOf || '')) problems.push('data/meta.json has no asOf date');
  if (!meta.generatedAt) problems.push('data/meta.json has no generatedAt');

  let rankings = null, clubs = null;
  try { rankings = await readJson(join(dataDir, 'rankings.json')); } catch { problems.push('data/rankings.json missing or invalid'); }
  try { clubs = await readJson(join(dataDir, 'clubs.json')); } catch { problems.push('data/clubs.json missing or invalid'); }
  if (rankings && !(Array.isArray(rankings.players) && rankings.players.length >= minPlayers)) problems.push(`rankings.json lists fewer than ${minPlayers} players`);
  if (clubs && !(Array.isArray(clubs) && clubs.length >= minClubs)) problems.push(`clubs.json lists fewer than ${minClubs} clubs`);

  // Any file flagged mock, anywhere in the data folder.
  let flagged = 0;
  for await (const f of jsonFiles(dataDir)) if (MOCK_MARK.test(await readFile(f, 'utf8'))) { flagged += 1; if (flagged <= 3) problems.push(`${f.slice(dataDir.length + 1)} is flagged "mock": true`); }
  if (flagged > 3) problems.push(`…and ${flagged - 3} more files flagged mock`);

  // Content check: the mock world is deterministic, so its ids are known. Real data must not contain them.
  if (rankings?.players?.length) {
    const mockIds = new Set(mock.rankings().players.map((p) => p.id));
    const clash = rankings.players.filter((p) => mockIds.has(p.id)).length;
    if (clash > 0) problems.push(`${clash} player ids in rankings.json are ids of the fictional mock world`);
  }
  return problems;
}

/* Everything a production build requires. Throws one Error listing every problem. */
export async function assertPublishable({ dataDir, siteUrl, approvalFile }) {
  const problems = [...problemsWithSiteUrl(siteUrl || '')];
  if (!approvalFile || !(await exists(approvalFile))) {
    problems.push(`no publish approval: the owner creates ${approvalFile || 'the approval file'} by hand (JSON with approvedBy and date) once the data licence is settled and the ratings are checked`);
  } else {
    try {
      const a = await readJson(approvalFile);
      if (!a.approvedBy || !/^\d{4}-\d{2}-\d{2}$/.test(a.date || '')) problems.push('approval file needs approvedBy and date (YYYY-MM-DD)');
    } catch { problems.push('approval file is not valid JSON'); }
  }
  problems.push(...(await dataProblems(dataDir)));
  if (problems.length) throw new Error(`Refusing to build for production:\n  - ${problems.join('\n  - ')}`);
}
