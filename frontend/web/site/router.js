// Page changes without reloads: the stadium scene stays alive. Internal links, the tour and
// back/forward fetch the next page, swap in its <main>, styles and nameplate, and run its script;
// that script calls immersive() again, which flies the running scene to the new page's spot.
let installed = false, navCount = 0, busy = false;

export function install() {
  if (installed) return;
  installed = true;
  history.scrollRestoration = 'manual';
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

export async function go(href, { push = true } = {}) {
  if (busy) return;
  busy = true;
  const url = new URL(href, location.href);
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(String(response.status));
    const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
    if (push) history.pushState({}, '', url);
    document.title = doc.title;
    document.querySelectorAll('[data-page-style]').forEach((n) => n.remove());
    doc.head.querySelectorAll('style').forEach((s) => { const c = document.createElement('style'); c.textContent = s.textContent; c.dataset.pageStyle = ''; document.head.append(c); });
    doc.head.querySelectorAll('link[rel="stylesheet"]').forEach((l) => {
      const h = l.getAttribute('href');
      if (!document.head.querySelector(`link[href="${h}"]`)) document.head.append(Object.assign(document.createElement('link'), { rel: 'stylesheet', href: h }));
    });
    document.body.className = doc.body.className;
    document.querySelector('.nameplate')?.remove();
    const plate = doc.querySelector('.nameplate');
    if (plate) document.querySelector('.page').before(document.adoptNode(plate));
    document.querySelector('.next-stop')?.remove();
    const main = document.adoptNode(doc.querySelector('main'));
    main.classList.add('is-arriving');
    document.querySelector('main').replaceWith(main);
    requestAnimationFrame(() => requestAnimationFrame(() => main.classList.remove('is-arriving')));
    window.scrollTo({ top: 0, behavior: 'instant' });
    document.querySelectorAll('.site-header nav a').forEach((a) => {
      if (new URL(a.href).pathname === url.pathname) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    navCount += 1;
    doc.querySelectorAll('script[type="module"]').forEach((s) => {
      const n = document.createElement('script');
      n.type = 'module';
      if (s.getAttribute('src')) n.src = `${s.getAttribute('src')}?nav=${navCount}`;   // a fresh URL so it runs again
      else n.textContent = s.textContent;
      n.dataset.pageScript = '';
      document.body.append(n);
    });
    if (url.hash) setTimeout(() => document.querySelector(url.hash)?.scrollIntoView(), 400);
  } catch {
    location.href = url.href;   // anything unexpected: fall back to a normal page load
  } finally {
    busy = false;
  }
}
