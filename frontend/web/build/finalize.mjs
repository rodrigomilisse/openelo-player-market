// The last step for every HTML file: set its robots tag from policy, and (production, indexable only) its canonical URL,
// absolute share image and structured data. Existing robots tags are removed first, so a source file cannot override policy.
import { esc } from './render.mjs';

export const urlOf = (file, siteUrl, pretty = true) => {
  if (file === 'index.html') return `${siteUrl}/`;
  return `${siteUrl}/${pretty ? file.replace(/\.html$/, '') : file}`;
};

function absolutise(node, siteUrl, pretty) {
  if (Array.isArray(node)) return node.map((n) => absolutise(n, siteUrl, pretty));
  if (node && typeof node === 'object') {
    if (Object.keys(node).length === 1 && 'file' in node) return node.file === '' ? `${siteUrl}/` : urlOf(node.file, siteUrl, pretty);
    return Object.fromEntries(Object.entries(node).map(([k, v]) => [k, absolutise(v, siteUrl, pretty)]));
  }
  return node;
}

export function finalize(html, { file, mode, robots, siteUrl, pretty = true, jsonld = [] }) {
  let out = html.replace(/[ \t]*<meta\s+name="robots"[^>]*>\n?/gi, '').replace(/[ \t]*<meta\s+name="openelo-build"[^>]*>\n?/gi, '')
    .replace(/[ \t]*<link\s+rel="canonical"[^>]*>\n?/gi, '').replace(/[ \t]*<script type="application\/ld\+json">[\s\S]*?<\/script>\n?/g, '');
  out = out.replace(/<meta charset="utf-8">/i, `<meta charset="utf-8">\n<meta name="robots" content="${robots}">\n<meta name="openelo-build" content="${mode}">`);
  if (!out.includes('name="robots"')) throw new Error(`${file}: no <meta charset> to anchor the robots tag`);
  const indexable = mode === 'production' && /^index\b/.test(robots) ;
  if (indexable) {
    const url = urlOf(file, siteUrl, pretty);
    const head = [`<link rel="canonical" href="${esc(url)}">`, `<meta property="og:url" content="${esc(url)}">`];
    const graph = jsonld.length ? `<script type="application/ld+json">${JSON.stringify({ '@context': 'https://schema.org', '@graph': absolutise(jsonld, siteUrl, pretty) }).replace(/</g, '\\u003c')}</script>` : '';
    out = out.replace(/(<meta property="og:image" content=")(?!https?:)([^"]*)(")/, `$1${esc(siteUrl)}/$2$3`)
      .replace('</head>', `${head.join('\n')}\n${graph}\n</head>`);
  }
  return out;
}
