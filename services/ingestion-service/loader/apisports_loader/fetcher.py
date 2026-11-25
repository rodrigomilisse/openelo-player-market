"""One rule for every call: look in Postgres first, ask the API only if the ledger has no answer."""

from . import db
from .client import Blocked, Client


class Fetcher:
    def __init__(self, conn, client: Client, refetch: bool = False, retry_blocked: bool = False):
        self.conn, self.client = conn, client
        self.refetch, self.retry_blocked = refetch, retry_blocked
        self.cached = 0       # answered from Postgres, no request spent
        self.fetched = 0
        self.blocked = 0

    def get(self, endpoint: str, params: dict, final):
        """Returns (payload_id, items), or None when the provider refuses this request.

        `final(items)` says whether the answer is complete; only complete answers are
        remembered as done. Raises client.QuotaExhausted when the budget runs out."""
        key = db.params_key(params)
        if not self.refetch:
            hit = db.stored_payload(self.conn, endpoint, key)
            if hit:
                self.cached += 1
                return hit[0], (hit[1].get("response") or [])
            if db.is_blocked(self.conn, endpoint, key) and not self.retry_blocked:
                self.blocked += 1
                return None
        try:
            response = self.client.get(endpoint, params)
        except Blocked as blocked:
            db.save_block(self.conn, endpoint, key, blocked.reason, blocked.detail)
            self.blocked += 1
            return None
        db.clear_block(self.conn, endpoint, key)
        payload_id = db.save_payload(self.conn, endpoint, params, response.body, response.results,
                                     final(response.items), response.remaining_day)
        self.fetched += 1
        return payload_id, response.items
