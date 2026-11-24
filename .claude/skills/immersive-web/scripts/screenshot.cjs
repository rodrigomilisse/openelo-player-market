// Screenshot pages of a served site in the four states that matter: desktop dark, desktop light,
// phone, and reduced motion. Reports console errors, failed requests and horizontal scroll.
//
//   node screenshot.cjs <base-url> <out-dir> [page ...]
//   node screenshot.cjs http://localhost:8000/ shots index.html about.html
//
// Environment:
//   THEME_KEY   localStorage key the site reads its theme from (default: site-theme)
//   THREE_DIR   folder holding node_modules/three, served in place of jsDelivr when the CDN is
//               blocked (as in Claude Code cloud sessions): npm install three@<version> there first
//   THREE_VER   the three version in the page's import map (default: 0.160.0)
//   SCROLL      pixels to scroll before each shot (default: 0)
//   SETTLE      milliseconds to wait for the scene to settle (default: 2500)
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const [, , base, out = 'shots', ...pages] = process.argv;
if (!base) { console.error('usage: node screenshot.cjs <base-url> <out-dir> [page ...]'); process.exit(2); }
const THEME_KEY = process.env.THEME_KEY || 'site-theme';
const THREE_DIR = process.env.THREE_DIR;
const THREE_VER = process.env.THREE_VER || '0.160.0';
const SCROLL = Number(process.env.SCROLL || 0);
const SETTLE = Number(process.env.SETTLE || 2500);

const STATES = [
  { name: 'desktop-dark', viewport: { width: 1440, height: 900 }, theme: 'dark' },
  { name: 'desktop-light', viewport: { width: 1440, height: 900 }, theme: 'light' },
  { name: 'phone', viewport: { width: 390, height: 844 }, theme: 'dark' },
  { name: 'reduced', viewport: { width: 1440, height: 900 }, theme: 'dark', reducedMotion: 'reduce' },
];

(async () => {
  fs.mkdirSync(out, { recursive: true });
  // SwiftShader gives headless Chromium a software WebGL.
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  let problems = 0;
  for (const page of pages.length ? pages : ['']) {
    for (const s of STATES) {
      const context = await browser.newContext({ viewport: s.viewport, deviceScaleFactor: 1, reducedMotion: s.reducedMotion || 'no-preference' });
      await context.addInitScript(([key, theme]) => { try { localStorage.setItem(key, theme); } catch { /* blocked */ } }, [THEME_KEY, s.theme]);
      if (THREE_DIR) {
        const prefix = `/npm/three@${THREE_VER}/`;
        await context.route(`https://cdn.jsdelivr.net/npm/three@${THREE_VER}/**`, (route) => {
          const file = path.join(THREE_DIR, 'node_modules/three', new URL(route.request().url()).pathname.slice(prefix.length));
          return fs.existsSync(file) ? route.fulfill({ path: file, contentType: 'text/javascript' }) : route.abort();
        });
      }
      const tab = await context.newPage();
      const notes = [];
      tab.on('pageerror', (e) => notes.push(`error: ${e.message}`));
      tab.on('console', (m) => { if (m.type() === 'error') notes.push(`console: ${m.text()}`); });
      tab.on('requestfailed', (r) => notes.push(`failed: ${r.url()}`));
      tab.on('response', (r) => { if (r.status() >= 400) notes.push(`${r.status()}: ${r.url()}`); });
      await tab.goto(new URL(page, base).href, { waitUntil: 'networkidle' });
      if (SCROLL) await tab.mouse.wheel(0, SCROLL);
      await tab.waitForTimeout(SETTLE);
      if (await tab.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)) notes.push('horizontal scroll');
      const file = path.join(out, `${(page || 'index').replace(/[^\w.-]+/g, '_').replace(/\.html$/, '')}-${s.name}.png`);
      await tab.screenshot({ path: file });
      problems += notes.length;
      console.log(`${file}${notes.length ? `\n  ${notes.join('\n  ')}` : '  ok'}`);
      await context.close();
    }
  }
  await browser.close();
  process.exitCode = problems ? 1 : 0;
})();
