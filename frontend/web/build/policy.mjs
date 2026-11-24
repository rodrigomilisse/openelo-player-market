// What may be indexed, in one place. Both the build and the verifier read this file.
// Anything NOT matched by INDEXABLE is noindex, always. Adding a pattern here is a decision to publish those pages.

export const NOINDEX_ALL = 'noindex, nofollow';          // every page in a preview, and the pages below that never rank
export const NOINDEX_FOLLOW = 'noindex, follow';         // a generated page that exists but is too thin to rank (a fringe player)
export const INDEX = 'index, follow';

// Pages a production build may mark indexable. Never: the market, compare, the query-string pages, rankings.html (the
// filter tool; the paginated rankings-*.html lists are what ranks), 404, privacy and terms (drafts until reviewed).
export const INDEXABLE = [
  /^index\.html$/, /^how\.html$/, /^leagues\.html$/, /^about\.html$/,
  /^player-[a-z0-9-]+\.html$/, /^club-[a-z0-9-]+\.html$/,
  /^rankings-[a-z0-9-]+-\d+\.html$/, /^week-\d{4}-\d{2}-\d{2}\.html$/,
];
export const mayBeIndexed = (file) => INDEXABLE.some((re) => re.test(file));

// Hosts that are previews or placeholders, never the public address.
export const BLOCKED_HOSTS = [/^localhost$/, /^127\./, /^\d+\.\d+\.\d+\.\d+$/, /\.pages\.dev$/, /\.netlify\.app$/, /\.workers\.dev$/, /\.vercel\.app$/, /(^|\.)example\.(com|org|net)$/, /\.local$/, /\.test$/];

export function problemsWithSiteUrl(siteUrl) {
  let u;
  try { u = new URL(siteUrl); } catch { return [`site URL "${siteUrl}" is not a URL`]; }
  const out = [];
  if (u.protocol !== 'https:') out.push(`site URL must be https, got ${u.protocol}`);
  if (BLOCKED_HOSTS.some((re) => re.test(u.hostname))) out.push(`site URL host ${u.hostname} is a preview or placeholder host, not the public domain`);
  if (u.pathname !== '/' || u.search || u.hash) out.push('site URL must be the bare origin, e.g. https://openelo.com');
  return out;
}

export const robotsOf = (html) => html.match(/<meta\s+name="robots"\s+content="([^"]*)"/i)?.[1] ?? null;
