// The site's only data access. Every function returns the read-API shape (README.md "Data contract").
// Real ratings when the site has a data/ folder (pipeline/export.py writes it); the mock world otherwise.
// The market is a play-money preview either way: over real ratings its prices are still simulated.
import * as mock from './mock.js';
import { CONFIG } from './config.js';

const fetchJson = (path) => fetch(`data/${path}`).then((r) => (r.ok ? r.json() : null)).catch(() => null);
const meta = await fetchJson('meta.json');
// Only data that says it is real counts as real. A meta.json without source: 'real' is treated as mock (and noindex).
const real = !!meta && meta.source === 'real' && meta.mock !== true;
// A production build never falls back to the mock world: better a broken page than fictional players on a public domain.
if (CONFIG.production && !real) throw new Error('OpenElo: production build without real data (data/meta.json source "real").');

const cache = new Map();
const get = (path) => { if (!cache.has(path)) cache.set(path, fetchJson(path)); return cache.get(path); };

/* A simulated share price from a rating series, the same shape as the mock's (until the market exists). */
function simulatedPrice(id, ratings, dates) {
  let h = [...id].reduce((x, c) => (x * 31 + c.charCodeAt(0)) | 0, 7);
  const rnd = () => ((h = (h * 1103515245 + 12345) | 0) >>> 0) / 4294967296;
  let price = Math.exp((ratings[0] - 1650) / 160);
  return ratings.map((r, i) => {
    const fair = Math.exp((r - 1650) / 160);
    price = price + (fair - price) * 0.35 + (rnd() - 0.5) * 0.04 * fair;
    return { date: dates[i], price: Math.round(Math.max(0.05, price) * 100) / 100 };
  });
}
const withPrice = (p) => p && { ...p, price: p.price || simulatedPrice(p.id, p.history.map((x) => x.rating), p.history.map((x) => x.date)) };

if (real) {   // the market preview runs over the real players
  const r = await get('rankings.json');
  const players = r.players.map((p) => {
    const ratings = [p.rating - p.season, p.rating - p.week, p.rating];
    return { id: p.id, name: p.name, rating: p.rating, position: p.position, club: { id: p.clubId, name: p.club, league: { name: p.league } },
      price: simulatedPrice(p.id, [...Array(9).fill(ratings[0]).map((x, i) => x + (ratings[1] - x) * i / 9), ratings[1], ratings[2]], Array(11).fill(r.asOf)) };
  });
  mock.useMarketWorld({ players, ranked: players, asOf: r.asOf });
}

export const isMock = !real;
export const getPlayer = async (id) => (real ? withPrice(await get(`players/${id}.json`)) : mock.player(id));
export const getClub = async (id) => (real ? get(`clubs/${id}.json`) : mock.club(id));
export const getRankings = async () => (real ? get('rankings.json') : mock.rankings());
export const getClubs = async () => (real ? get('clubs.json') : mock.clubs());
export const getLeagues = async () => (real ? get('leagues.json') : mock.leagues());
export const getWeek = async () => (real ? get('week.json') : mock.week());
export async function search(query, limit = 8) {
  if (!real) return mock.search(query, limit);
  const q = mock.slug(query);
  if (!q) return [];
  const all = await get('search.json');
  const hits = all.filter((x) => x.id.includes(q));
  return [...hits.filter((x) => x.kind === 'club').slice(0, 4), ...hits.filter((x) => x.kind === 'player')].slice(0, limit);
}
export const getMarket = async () => mock.market();
export const getBook = async (id) => mock.book(id);
export const getQuote = async (id, side, amount) => mock.quote(id, side, amount);
export const getPool = async (extraWeight) => mock.pool(extraWeight);
export const getProjection = async (positions) => mock.projection(positions);
export const FEES = mock.FEES;

/* The play-money account lives in this browser only (FEATURES.md: accounts, wallet, positions).
   { credits, positions: { id: { shares, cost } }, watch: [ids], history: [{ at, kind, ... }], dividends } */
const WALLET_KEY = 'openelo-play-wallet';
const fresh = () => ({ credits: 1000, positions: {}, watch: [], history: [], dividends: 0, orders: [] });
export const SHARE_TERM_YEARS = 3;   // shares mature after this (money-model notes); placeholder until the rules are set
export function wallet() {
  try {
    const w = JSON.parse(localStorage.getItem(WALLET_KEY) || 'null');
    if (w && typeof w.credits === 'number') {
      if (w.holdings && !w.positions) {   // the first preview stored shares only
        w.positions = Object.fromEntries(Object.entries(w.holdings).map(([id, shares]) => [id, { shares, cost: 0 }]));
        delete w.holdings;
      }
      return { ...fresh(), ...w };
    }
  } catch { /* storage blocked */ }
  return fresh();
}
export function saveWallet(w) { try { localStorage.setItem(WALLET_KEY, JSON.stringify(w)); } catch { /* storage blocked: it lasts this visit */ } }

export function recordTrade(id, name, quote) {
  const w = wallet();
  const pos = w.positions[id] || { shares: 0, cost: 0 };
  if (quote.side === 'buy' && !pos.shares) pos.opened = Date.now();   // the term runs from the first buy (FEATURES.md: per-lot terms)
  if (quote.side === 'buy') {
    w.credits = Math.round((w.credits - quote.spent) * 100) / 100;
    pos.shares += quote.shares; pos.cost = Math.round((pos.cost + quote.spent) * 100) / 100;
  } else {
    w.credits = Math.round((w.credits + quote.received) * 100) / 100;
    pos.cost = pos.shares ? Math.round(pos.cost * (1 - quote.shares / pos.shares) * 100) / 100 : 0;
    pos.shares -= quote.shares;
  }
  w.positions[id] = pos;
  w.history.unshift({ at: Date.now(), kind: quote.side, id, name, shares: quote.shares, credits: quote.side === 'buy' ? -quote.spent : quote.received });
  saveWallet(w);
  return w;
}

export function toggleWatch(id) {
  const w = wallet();
  w.watch = w.watch.includes(id) ? w.watch.filter((x) => x !== id) : [...w.watch, id];
  saveWallet(w);
  return w.watch.includes(id);
}

/* Preview only: pay the next daily dividend now, as if the day had ended. */
export function simulatePayout() {
  const w = wallet();
  const pr = mock.projection(w.positions);
  if (!pr.next) return { paid: 0, rows: [] };
  w.credits = Math.round((w.credits + pr.next) * 100) / 100;
  w.dividends = Math.round((w.dividends + pr.next) * 100) / 100;
  for (const r of pr.rows) { const pos = w.positions[r.id]; pos.dividends = Math.round(((pos.dividends || 0) + r.next) * 100) / 100; }
  w.history.unshift({ at: Date.now(), kind: 'dividend', credits: pr.next, rows: pr.rows.map((r) => ({ id: r.id, name: r.name, credits: r.next })) });
  saveWallet(w);
  return { paid: pr.next, rows: pr.rows };
}

/* Limit orders (preview): kept in the wallet, filled when the book reaches the price.
   { id, playerId, name, side, shares, limit, at } */
export function placeOrder(order) {
  const w = wallet();
  w.orders = [...(w.orders || []), { ...order, id: `o${Date.now().toString(36)}`, at: Date.now() }];
  saveWallet(w);
  return checkOrders();
}
export function cancelOrder(orderId) {
  const w = wallet();
  w.orders = (w.orders || []).filter((o) => o.id !== orderId);
  saveWallet(w);
}
/* Fill whatever can fill now: a buy when someone sells at or under its limit, a sale when someone buys at or over. */
export function checkOrders() {
  const filled = [];
  for (const o of wallet().orders || []) {
    const b = mock.book(o.playerId);
    if (!b) continue;
    const w = wallet();
    const best = o.side === 'buy' ? b.asks[0]?.price : b.bids[0]?.price;
    if (best == null || (o.side === 'buy' ? best > o.limit : best < o.limit)) continue;
    const gross = o.shares * best;
    const fees = Math.round(gross * mock.FEES.taker * 100) / 100;
    if (o.side === 'buy' && gross + fees > w.credits) continue;
    if (o.side === 'sell' && (w.positions[o.playerId]?.shares || 0) < o.shares) continue;
    cancelOrder(o.id);
    recordTrade(o.playerId, o.name, o.side === 'buy' ? { side: 'buy', shares: o.shares, spent: Math.round((gross + fees) * 100) / 100 }
      : { side: 'sell', shares: o.shares, received: Math.round((gross - fees) * 100) / 100 });
    filled.push({ ...o, price: best });
  }
  return filled;
}
