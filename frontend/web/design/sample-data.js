// Fictional sample data shared by every design. Prices in credits, ratings in OpenElo points.

export const MINT_PRICE = 3.61;

export const mendonca = {
  name: 'Tiago Mendonça',
  short: 'Mendonça',
  club: 'Vale do Sado FC',
  position: 'Central midfield',
  number: 8,
  price: [1.00, 1.02, 1.05, 1.04, 1.10, 1.18, 1.15, 1.22, 1.30, 1.28, 1.35, 1.50, 1.62, 1.58, 1.75, 2.10, 2.55, 2.90, 3.05, 2.85, 2.95, 3.10, 3.30, 3.55, 3.70, 3.48, 3.36, 3.44, 3.39, 3.42],
  elo: [1700, 1702, 1705, 1703, 1708, 1712, 1710, 1716, 1722, 1720, 1726, 1738, 1748, 1745, 1756, 1767, 1778, 1790, 1797, 1791, 1796, 1798, 1800, 1812, 1821, 1824, 1826, 1836, 1838, 1842]
};

// The last seven days in finer steps, for the trading view. The match is Saturday's 2–1.
export const week = {
  price: [3.10, 3.12, 3.08, 3.15, 3.22, 3.30, 3.26, 3.35, 3.48, 3.56, 3.60, 3.55, 3.50, 3.44, 3.47, 3.52, 3.49, 3.41, 3.38, 3.43, 3.46, 3.40, 3.36, 3.39, 3.44, 3.47, 3.43, 3.40, 3.41, 3.42],
  elo: [1819, 1819, 1819, 1820, 1821, 1821, 1821, 1821, 1830, 1830, 1830, 1830, 1830, 1830, 1830, 1832, 1832, 1832, 1832, 1836, 1836, 1836, 1836, 1838, 1838, 1838, 1840, 1840, 1842, 1842],
  matchIndex: 8
};

// index = position in the series above, change = rating points
export const matches = [
  { index: 11, score: '2–0', opponent: 'Sporting Arade', venue: 'home', change: 12, minutes: 90, note: 'Ran the midfield' },
  { index: 15, score: '3–0', opponent: 'União Litoral', venue: 'home', change: 11, minutes: 90, note: 'Scored, biggest jump of his season' },
  { index: 19, score: '0–2', opponent: 'FC Montebravo', venue: 'away', change: -6, minutes: 78, note: 'Quiet game, subbed off' },
  { index: 22, score: '1–1', opponent: 'CD Ribamar', venue: 'away', change: 2, minutes: 90, note: 'Steady' },
  { index: 24, score: '2–1', opponent: 'Atlético Serrano', venue: 'home', change: 9, minutes: 90, note: 'Assisted the winner, man of the match' }
];

export const fixtures = [
  { when: 'Sat 21 Nov', opponent: 'Estrela do Mar', venue: 'home' },
  { when: 'Wed 25 Nov', opponent: 'CD Ribamar', venue: 'away' },
  { when: 'Sun 29 Nov', opponent: 'FC Montebravo', venue: 'home' }
];

export const book = {
  asks: [['3.55', 40], ['3.52', 85], ['3.49', 210], ['3.46', 60]],
  bids: [['3.40', 150], ['3.37', 90], ['3.34', 300], ['3.31', 45]]
};

function walk(seed, start, drift, length) {
  let state = seed;
  const random = () => (state = (state * 16807) % 2147483647) / 2147483647;
  const series = [start];
  for (let i = 1; i < length; i++) series.push(Math.max(0.3, series[i - 1] * (1 + drift + (random() - 0.5) * 0.09)));
  return series;
}

function ratingWalk(seed, start, drift, length) {
  let state = seed;
  const random = () => (state = (state * 48271) % 2147483647) / 2147483647;
  const series = [start];
  for (let i = 1; i < length; i++) series.push(Math.round(series[i - 1] + drift + (random() - 0.5) * 14));
  return series;
}

export const market = [
  { ...mendonca, change: 4.3, heat: 12.8, held: 40, costBasis: 2.10 },
  { name: 'Bruno Esteves', short: 'Esteves', club: 'Atlético Serrano', position: 'Striker', number: 9, price: walk(11, 3.9, 0.01, 30), elo: ratingWalk(5, 1820, 1.2, 30), change: 0.8, heat: 3.1, held: 12, costBasis: 4.80 },
  { name: 'André Couto', short: 'Couto', club: 'CD Ribamar', position: 'Centre back', number: 5, price: walk(23, 4.3, -0.001, 30), elo: ratingWalk(9, 1795, 0.2, 30), change: 0.2, heat: 0.9, held: 25, costBasis: 4.40 },
  { name: 'Nuno Vidal', short: 'Vidal', club: 'União Litoral', position: 'Winger', number: 7, price: walk(37, 1.6, 0.017, 30), elo: ratingWalk(13, 1690, 2.4, 30), change: 2.1, heat: 7.4, held: 30, costBasis: 1.95 },
  { name: 'Rui Calado', short: 'Calado', club: 'FC Montebravo', position: 'Full back', number: 4, price: walk(41, 2.3, -0.008, 30), elo: ratingWalk(17, 1760, -1.4, 30), change: -1.2, heat: 0.4, held: 18, costBasis: 2.30 },
  { name: 'Diogo Serra', short: 'Serra', club: 'Sporting Arade', position: 'Goalkeeper', number: 1, price: walk(53, 1.4, -0.012, 30), elo: ratingWalk(21, 1730, -1.8, 30), change: -3.4, heat: 0.2, held: 0, costBasis: 0 }
];
