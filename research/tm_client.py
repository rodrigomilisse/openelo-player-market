"""Direct Transfermarkt client.

Scrapes transfermarkt.com directly rather than going through a third-party
hosted wrapper (the public demo of felipeall/transfermarkt-api was found to
be unreliable — 500s — while transfermarkt.com itself was fine). Two pages
are used, both confirmed working against the current site markup:

- Player search: HTML page parsed with XPath (selectors mirror
  felipeall/transfermarkt-api's, which is a good sign they're durable).
- Market value history: `ceapi/marketValueDevelopment/graph/{id}`, an
  internal JSON endpoint the site's own market-value chart widget calls —
  no HTML parsing needed, and it survived the recent frontend rewrite that
  broke scrapers relying on the old inline Highcharts markup.

If Transfermarkt changes markup again, only this file should need to change.
"""

import datetime
import re
import time
from urllib.parse import quote

import requests
from lxml import html

BASE_URL = "https://www.transfermarkt.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 20
MAX_RETRIES = 4
RETRY_BACKOFF_SECONDS = 3

SEARCH_URL = BASE_URL + "/schnellsuche/ergebnis/schnellsuche?query={query}&Spieler_page=1"
MARKET_VALUE_URL = BASE_URL + "/ceapi/marketValueDevelopment/graph/{player_id}"

XPATH_SEARCH_ROWS = "//div[@class='box'][h2[contains(text(), 'players')]]//tbody//tr[@class='odd' or @class='even']"
XPATH_ID = ".//td[@class='hauptlink']//a/@href"
XPATH_NAME = ".//td[@class='hauptlink']//a//@title"
XPATH_POSITION = ".//td[@class='zentriert'][1]//text()"
XPATH_CLUB_NAME = ".//img[@class='tiny_wappen']//@title"
XPATH_AGE = ".//td[@class='zentriert'][3]//text()"
XPATH_MARKET_VALUE = ".//td[@class='rechts hauptlink']//text()"

ID_FROM_HREF_RE = re.compile(r"/spieler/(\d+)")


class TransfermarktClientError(Exception):
    pass


def _get(url: str, as_json: bool) -> "requests.Response | dict":
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                return resp.json() if as_json else resp
            if resp.status_code in (429, 500, 502, 503, 504):
                last_exc = TransfermarktClientError(f"{resp.status_code} from {url}")
            else:
                resp.raise_for_status()
        except requests.RequestException as exc:
            last_exc = exc
        time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise TransfermarktClientError(f"Failed after {MAX_RETRIES} attempts: {url}") from last_exc


def search_player(name: str) -> list[dict]:
    """Returns a list of dicts: id, name, position, club_name, age, market_value_text."""
    resp = _get(SEARCH_URL.format(query=quote(name)), as_json=False)
    tree = html.fromstring(resp.content)
    rows = tree.xpath(XPATH_SEARCH_ROWS)

    results = []
    for row in rows:
        hrefs = row.xpath(XPATH_ID)
        if not hrefs:
            continue
        match = ID_FROM_HREF_RE.search(hrefs[0])
        if not match:
            continue
        names = row.xpath(XPATH_NAME)
        positions = row.xpath(XPATH_POSITION)
        clubs = row.xpath(XPATH_CLUB_NAME)
        ages = row.xpath(XPATH_AGE)
        market_values = row.xpath(XPATH_MARKET_VALUE)
        results.append(
            {
                "id": match.group(1),
                "name": names[0].strip() if names else None,
                "position": positions[0].strip() if positions else None,
                "club_name": clubs[0].strip() if clubs else None,
                "age": ages[0].strip() if ages else None,
                "market_value_text": market_values[0].strip() if market_values else None,
            }
        )
    return results


def get_market_value_history(tm_id: str) -> list[dict]:
    """Returns [{'date': 'YYYY-MM-DD', 'marketValue': int_eur, 'clubName': str, 'age': int}, ...]."""
    data = _get(MARKET_VALUE_URL.format(player_id=tm_id), as_json=True)
    history = []
    for entry in data.get("list", []):
        raw_date = entry.get("datum_mw")
        try:
            iso_date = datetime.datetime.strptime(raw_date, "%d/%m/%Y").date().isoformat()
        except (TypeError, ValueError):
            continue
        history.append(
            {
                "date": iso_date,
                "marketValue": entry.get("y"),
                "clubName": entry.get("verein"),
                "age": int(entry["age"]) if str(entry.get("age", "")).isdigit() else None,
            }
        )
    return history
