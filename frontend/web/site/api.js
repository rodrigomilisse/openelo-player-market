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
export const FEES = mock.FEES;
export const isMock = true;

/* The play-money wallet lives in this browser only. */
const WALLET_KEY = 'openelo-play-wallet';
export function wallet() {
  try { const w = JSON.parse(localStorage.getItem(WALLET_KEY) || 'null'); if (w && typeof w.credits === 'number') return w; } catch { /* storage blocked */ }
  return { credits: 1000, holdings: {}, history: [] };
}
export function saveWallet(w) { try { localStorage.setItem(WALLET_KEY, JSON.stringify(w)); } catch { /* storage blocked: the trade lasts this visit */ } }
