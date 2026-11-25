"""API-Football client that knows the quota and never spends it blindly."""

import os
import time

import requests

DEFAULT_BASE = "https://v3.football.api-sports.io"


class QuotaExhausted(Exception):
    """The day's requests, or the budget given to this run, are used up. Not an error."""


class Blocked(Exception):
    """The provider refuses this request for a lasting reason (the plan does not cover it)."""

    def __init__(self, reason: str, detail: str):
        super().__init__(f"{reason}: {detail}")
        self.reason, self.detail = reason, detail


class Fatal(Exception):
    """Nothing will work until the user acts (suspended account, bad key)."""


class Response:
    def __init__(self, body: dict, remaining_day: int | None):
        self.body, self.remaining_day = body, remaining_day

    @property
    def items(self) -> list:
        return self.body.get("response") or []

    @property
    def results(self) -> int:
        return len(self.items)


class Client:
    def __init__(self, base: str | None = None, key: str | None = None, proxy_token: str | None = None,
                 max_requests: int | None = None, reserve: int = 3, session=None, sleep=time.sleep):
        self.base = (base or os.environ.get("APISPORTS_BASE") or DEFAULT_BASE).rstrip("/")
        key = key or os.environ.get("APISPORTS_KEY")
        token = proxy_token or os.environ.get("APISPORTS_PROXY_TOKEN")
        self.headers = {}
        if key:
            self.headers["x-apisports-key"] = key
        if token:  # a dedicated-IP proxy in front of the API (see README)
            self.headers["Authorization"] = f"Bearer {token}"
        self.session = session or requests.Session()
        self.sleep = sleep
        self.reserve = reserve
        self.budget = max_requests          # None = only the daily quota limits the run
        self.used = 0
        self.remaining_day = None           # learned from the first response or /status

    def _check_errors(self, body: dict) -> None:
        errors = body.get("errors")
        if not errors:
            return
        if isinstance(errors, list):
            errors = {str(i): e for i, e in enumerate(errors)}
        text = "; ".join(f"{k}: {v}" for k, v in errors.items())
        if "access" in errors or "token" in errors:
            raise Fatal(f"{text}\nThe account is suspended or the key is wrong. A suspension is usually caused by "
                        f"a shared outbound IP (cloud/serverless): send requests through a dedicated static IP "
                        f"and set APISPORTS_BASE to it (README, 'Suspended account').")
        if "requests" in errors:
            raise QuotaExhausted(text)
        if "plan" in errors:
            raise Blocked("plan", text)
        raise RuntimeError(f"API error: {text}")

    def status(self) -> dict:
        """Account state. The provider does not count this call against the quota."""
        body = self._http("status", {})
        self._check_errors(body)
        info = body.get("response") or {}
        req = info.get("requests", {})
        if req:
            self.remaining_day = req["limit_day"] - req["current"]
        return info

    def _http(self, endpoint: str, params: dict):
        response = self.session.get(f"{self.base}/{endpoint}", params=params, headers=self.headers, timeout=60)
        if response.status_code in (401, 403):
            raise Fatal(f"HTTP {response.status_code} from the API or proxy: check the key / proxy token")
        response.raise_for_status()
        self._last_headers = response.headers
        return response.json()

    def get(self, endpoint: str, params: dict) -> Response:
        if self.budget is not None and self.used >= self.budget:
            raise QuotaExhausted(f"this run's budget of {self.budget} requests is used")
        if self.remaining_day is not None and self.remaining_day <= self.reserve:
            raise QuotaExhausted(f"{self.remaining_day} requests left today (reserve {self.reserve})")
        for attempt in range(4):
            body = self._http(endpoint, params)
            errors = body.get("errors")
            if isinstance(errors, dict) and "rateLimit" in errors:   # per-minute limit: wait, retry
                self.sleep(61)
                continue
            break
        self._check_errors(body)
        self.used += 1
        headers = self._last_headers
        left = headers.get("x-ratelimit-requests-remaining")
        if left is not None:
            self.remaining_day = int(left)
        if headers.get("x-ratelimit-remaining") == "0":            # per-minute allowance spent
            self.sleep(61)
        return Response(body, self.remaining_day)
