// Shared by the Market pages: the directors'-box scene, money formatting, and the reader's positions priced now.
import { immersive, squadFormation, fieldFormation, BOX } from './scene.js';
import { getMarket, getProjection, wallet } from './api.js';

export const cr = (v) => (Math.round(v * 100) / 100).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const signedCr = (v) => (v > 0.004 ? `+${cr(v)}` : v < -0.004 ? `−${cr(-v)}` : '0.00');
export const tone = (v) => (v > 0.004 ? 'gain' : v < -0.004 ? 'loss' : '');
export const tradeUrl = (id) => `trade.html?id=${encodeURIComponent(id)}`;

export function spark(values, { w = 100, h = 26 } = {}) {
  const lo = Math.min(...values), hi = Math.max(...values);
  const d = values.map((v, i) => `${i ? 'L' : 'M'}${(i / (values.length - 1)) * w},${h - 3 - ((v - lo) / (hi - lo || 1)) * (h - 6)}`).join('');
  return `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true"><path d="${d}" fill="none" stroke="var(--up)" stroke-width="1.6"/></svg>`;
}

let marketCache = null;
export async function marketById() {
  if (!marketCache) { const m = await getMarket(); marketCache = new Map(m.players.map((p) => [p.id, p])); }
  return marketCache;
}

/* Everything the reader holds, priced now, with the next payout if ratings stay as they are. */
export async function portfolio() {
  const w = wallet();
  const byId = await marketById();
  const proj = await getProjection(w.positions);
  const next = new Map(proj.rows.map((r) => [r.id, r]));
  const rows = Object.entries(w.positions).filter(([, x]) => x.shares > 0).map(([id, x]) => ({ id, ...x, p: byId.get(id), proj: next.get(id) })).filter((x) => x.p)
    .map((x) => ({ ...x, value: x.shares * x.p.price, gain: x.shares * x.p.price - x.cost }));
  rows.sort((a, b) => b.value - a.value);
  const value = rows.reduce((s, x) => s + x.value, 0), cost = rows.reduce((s, x) => s + x.cost, 0);
  return { w, rows, proj, value, cost, gain: value - cost };
}

/* The box: your squad below, lit by what each player will pay next. */
export async function boxScene() {
  const { rows } = await portfolio();
  const top = Math.max(0, ...rows.map((r) => r.proj?.next || 0));
  const squad = squadFormation(rows.map((r) => ({ position: r.p.position, shares: r.shares, brightness: top ? (r.proj?.next || 0) / top : 0 })));
  immersive({
    formations: [squad, squad, fieldFormation()],
    palette: ['#FFD66B', '#FFD66B', '#7FA7D8'], alt: '#5A7AA8', spark: '#FFE9A8', dim: rows.length ? 0.55 : 0.35, shiftRight: 0,
    keyframes: BOX,
  });
}

export function countdown(el, at) {
  const tick = () => {
    if (!el.isConnected && !document.contains(el)) return;
    const s = Math.max(0, Math.round((at - Date.now()) / 1000));
    el.textContent = `${Math.floor(s / 3600)}h ${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}m ${String(s % 60).padStart(2, '0')}s`;
  };
  tick();
  return setInterval(tick, 1000);
}
