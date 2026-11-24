// Page changes without reloads: the stadium scene stays alive. Internal links, the tour and
// back/forward fetch the next page, swap in its <main>, styles and nameplate, and run its script;
// that script calls immersive() again, which flies the running scene to the new page's spot.
let installed = false, navCount = 0, busy = false;
// Every visited page stays alive: its <main> (with its charts, listeners and state), nameplate, styles and
// the scene options it gave. Returning to it just puts it back and re-targets the scene.
const views = new Map();
const pages = new Map();   // prefetched HTML by URL
let currentScene = null;
const keyOf = (u) => u.pathname + u.search;

/* scene.js reports what the page asked of the scene, so a revisit can restore it without the script. */
export function rememberScene(options) { currentScene = options; }

export function prefetch(href) {
  const url = new URL(href, location.href);
  if (views.has(keyOf(url)) || pages.has(url.href) || url.origin !== location.origin) return;
  pages.set(url.href, fetch(url).then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status))))).catch(() => { pages.delete(url.href); return null; }));
}

export function install() {
  if (installed) return;
  installed = true;
  history.scrollRestoration = 'manual';
  document.querySelectorAll('head style').forEach((st) => { st.dataset.pageStyle = ''; });   // the first page's own styles swap like any other
  const hover = (e) => { const a = e.target.closest?.('a[href]'); if (a && /\.html/.test(a.getAttribute('href'))) prefetch(a.href); };
  document.addEventListener('pointerover', hover, { passive: true });
  document.addEventListener('focusin', hover);
  document.addEventListener('click', (e) => {
    const a = e.target.closest?.('a[href]');
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || a.target || a.hasAttribute('download')) return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin || !/\.html$/.test(url.pathname) || dir(url) !== dir(location)) return;
    if (url.pathname === location.pathname && url.search === location.search) return;   // same page: let anchors work
    e.preventDefault();
    go(url.href);
  });
  window.addEventListener('popstate', () => go(location.href, { push: false }));
}

const dir = (u) => u.pathname.slice(0, u.pathname.lastIndexOf('/') + 1);

function saveCurrent() {
  const main = document.querySelector('main');
  if (!main) return;
  views.set(keyOf(location), {
    main, plate: document.querySelector('.nameplate'), title: document.title, bodyClass: document.body.className, bodyStyle: document.body.getAttribute('style') || '',
    styles: [...document.querySelectorAll('[data-page-style]')].map((n) => n.textContent), scene: currentScene, scrollY: window.scrollY,
  });
}

function setNav(url) {
  document.querySelectorAll('.site-header nav a, .tabbar a').forEach((a) => {
    if (new URL(a.href).pathname === url.pathname) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
}

function swapIn({ main, plate, styles, title, bodyClass, bodyStyle = '' }) {
  document.title = title;
  document.querySelectorAll('[data-page-style]').forEach((n) => n.remove());
  styles.forEach((text) => { const c = document.createElement('style'); c.textContent = text; c.dataset.pageStyle = ''; document.head.append(c); });
  document.body.className = bodyClass;
  document.body.setAttribute('style', bodyStyle);   // page-set variables, like the player page's plate width
  document.querySelector('.nameplate')?.remove();
  if (plate) document.querySelector('.page').before(plate);
  document.querySelector('.next-stop')?.remove();
  main.classList.add('is-arriving');
  document.querySelector('main').replaceWith(main);
  requestAnimationFrame(() => requestAnimationFrame(() => main.classList.remove('is-arriving')));
}

export async function go(href, { push = true } = {}) {
  if (busy) return;
  busy = true;
  const url = new URL(href, location.href);
  try {
    const kept = views.get(keyOf(url));
    if (kept && kept.scene) {   // a page already visited: put it back as it was
      saveCurrent();
      if (push) history.pushState({}, '', url);
      swapIn(kept);
      window.scrollTo({ top: push ? 0 : kept.scrollY, behavior: 'instant' });
      setNav(url);
      currentScene = kept.scene;
      const { immersive } = await import('./scene.js');
      immersive(kept.scene);
      kept.main.dispatchEvent(new CustomEvent('pageshow-again', { bubbles: false }));   // pages refresh anything personal, like a wallet
      if (url.hash) setTimeout(() => document.querySelector(url.hash)?.scrollIntoView(), 400);
      window.dispatchEvent(new Event('openelo:navigate'));
      return;
    }
    prefetch(url.href);
    const html = await pages.get(url.href);
    pages.delete(url.href);
    if (!html) throw new Error('fetch failed');
    const doc = new DOMParser().parseFromString(html, 'text/html');
    saveCurrent();
    if (push) history.pushState({}, '', url);
    const plate = doc.querySelector('.nameplate');
    swapIn({ main: document.adoptNode(doc.querySelector('main')), plate: plate ? document.adoptNode(plate) : null,
      styles: [...doc.head.querySelectorAll('style')].map((st) => st.textContent), title: doc.title, bodyClass: doc.body.className });
    doc.head.querySelectorAll('link[rel="stylesheet"]').forEach((l) => {
      const h = l.getAttribute('href');
      if (!document.head.querySelector(`link[href="${h}"]`)) document.head.append(Object.assign(document.createElement('link'), { rel: 'stylesheet', href: h }));
    });
    window.scrollTo({ top: 0, behavior: 'instant' });
    setNav(url);
    currentScene = null;
    navCount += 1;
    doc.querySelectorAll('script[type="module"]').forEach((st) => {
      const n = document.createElement('script');
      n.type = 'module';
      if (st.getAttribute('src')) n.src = `${st.getAttribute('src')}?nav=${navCount}`;   // a fresh URL so it runs again
      else n.textContent = st.textContent;
      document.body.append(n);
    });
    if (url.hash) setTimeout(() => document.querySelector(url.hash)?.scrollIntoView(), 400);
    window.dispatchEvent(new Event('openelo:navigate'));
  } catch {
    location.href = url.href;   // anything unexpected: fall back to a normal page load
  } finally {
    busy = false;
  }
}
