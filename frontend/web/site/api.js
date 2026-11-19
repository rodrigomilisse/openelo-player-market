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
export const isMock = true;
