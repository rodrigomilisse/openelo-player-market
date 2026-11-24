// Order form behaviour for the mockups. Money is handled in whole hundredths of a credit, never floats.
import { book, MINT_PRICE } from './sample-data.js';

const FEE_PERCENT = 5;
const MINT_HUNDREDTHS = Math.round(MINT_PRICE * 100);
const levels = (rows) => rows.map(([price, shares]) => [Math.round(Number(price) * 100), shares]);
const ASKS = levels(book.asks);
const BIDS = levels(book.bids);
export const BEST_ASK = Math.min(...ASKS.map(([p]) => p));
export const BEST_BID = Math.max(...BIDS.map(([p]) => p));
const total = (rows) => rows.reduce((sum, [, shares]) => sum + shares, 0);

// What a limit order at this price would do against the sample book.
// kind: 'mint' (new shares are no dearer), 'fills' (shares that match now) or 'waits' (shares queued ahead).
export function bookOutcome(side, priceHundredths) {
  if (side === 'buy') {
    if (priceHundredths >= MINT_HUNDREDTHS) return { kind: 'mint' };
    if (priceHundredths >= BEST_ASK) return { kind: 'fills', shares: total(ASKS.filter(([p]) => p <= priceHundredths)) };
    return { kind: 'waits', shares: total(BIDS.filter(([p]) => p >= priceHundredths)), best: BEST_ASK };
  }
  if (priceHundredths <= BEST_BID) return { kind: 'fills', shares: total(BIDS.filter(([p]) => p >= priceHundredths)) };
  return { kind: 'waits', shares: total(ASKS.filter(([p]) => p <= priceHundredths)), best: BEST_BID };
}

export function quote(shares, priceHundredths) {
  const cost = shares * priceHundredths;
  return { cost, fee: Math.floor((cost * FEE_PERCENT + 50) / 100) };
}

export function toHundredths(text) {
  const match = /^\s*(\d+)(?:\.(\d{1,2}))?\s*$/.exec(text);
  if (!match) return null;
  return parseInt(match[1], 10) * 100 + parseInt(((match[2] || '') + '00').slice(0, 2), 10);
}

export function formatCredits(hundredths) {
  const whole = Math.floor(hundredths / 100);
  const rest = hundredths % 100;
  return `${whole.toLocaleString('en')}.${String(rest).padStart(2, '0')} cr`;
}

export function renderBook(container, rows, color) {
  container.innerHTML = rows.map(([price, shares]) =>
    `<div class="book-row"><div class="bar" style="width:${Math.round(shares / 3)}%;background:${color}"></div>` +
    `<span style="color:${color};font-weight:600">${price}</span><span>${shares}</span></div>`).join('');
}

// Expects the ids used by the ticket markup in matchnight.html and trade.html.
export function mountTicket(form, { mintHundredths }) {
  const field = (id) => form.querySelector(`#${id}`);
  let side = 'buy';

  function update() {
    const shares = parseInt(field('shares').value, 10);
    const mint = side === 'buy' && field('venue-mint').checked;
    const price = mint ? mintHundredths : toHundredths(field('limit').value);
    field('limit').disabled = mint;
    if (!(shares > 0) || price === null) {
      ['cost', 'fee', 'sum'].forEach((id) => { field(id).textContent = '–'; });
      return;
    }
    const { cost, fee } = quote(shares, price);
    field('cost').textContent = formatCredits(cost);
    field('fee').textContent = formatCredits(fee);
    field('sum').textContent = formatCredits(side === 'buy' ? cost + fee : cost - fee);
    field('sum-label').textContent = side === 'sell' ? 'You receive when filled' : mint ? 'You pay' : 'Held until filled';
  }

  function setSide(next) {
    side = next;
    field('side-buy').setAttribute('aria-pressed', String(next === 'buy'));
    field('side-sell').setAttribute('aria-pressed', String(next === 'sell'));
    field('venue-legend').textContent = next === 'buy' ? 'Buy from' : 'Sell to';
    field('venue-mint-row').hidden = next === 'sell';
    if (next === 'sell') field('venue-holders').checked = true;
    field('submit').textContent = next === 'buy' ? 'Place buy order' : 'Place sell order';
    field('submit').classList.toggle('sell', next === 'sell');
    field('notice').textContent = '';
    update();
  }

  field('side-buy').addEventListener('click', () => setSide('buy'));
  field('side-sell').addEventListener('click', () => setSide('sell'));
  ['shares', 'limit', 'venue-holders', 'venue-mint'].forEach((id) => {
    field(id).addEventListener('input', update);
    field(id).addEventListener('change', update);
  });
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    field('notice').textContent = 'Demo only: no order was sent.';
  });
  update();
}
