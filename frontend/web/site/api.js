// The site's only data access. Every function returns the read-API shape (README.md).
// Today everything comes from the mock world; when the rating service publishes real
// data, each function fetches it instead and the pages do not change.
import * as mock from './mock.js';

export const getPlayer = async (id) => mock.player(id);
export const getClub = async (id) => mock.club(id);
export const getRankings = async () => mock.rankings();
export const getClubs = async () => mock.clubs();
export const getLeagues = async () => mock.leagues();
export const getWeek = async () => mock.week();
export const search = async (query) => mock.search(query);
export const getMarket = async () => mock.market();
export const getBook = async (id) => mock.book(id);
export const getQuote = async (id, side, amount) => mock.quote(id, side, amount);
export const getPool = async (extraWeight) => mock.pool(extraWeight);
export const getProjection = async (positions) => mock.projection(positions);
export const FEES = mock.FEES;
export const isMock = true;

/* The play-money account lives in this browser only (FEATURES.md: accounts, wallet, positions).
   { credits, positions: { id: { shares, cost } }, watch: [ids], history: [{ at, kind, ... }], dividends } */
const WALLET_KEY = 'openelo-play-wallet';
const fresh = () => ({ credits: 1000, positions: {}, watch: [], history: [], dividends: 0 });
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
