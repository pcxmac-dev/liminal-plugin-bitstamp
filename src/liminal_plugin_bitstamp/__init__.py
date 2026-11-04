"""Bitstamp (bitstamp.net) for Liminal: crypto minute bars from 2011 and its public trade stream, no key;
an exchange of its own.

A Liminal plugin released on its own, a class on plugin API 2.0 (liminal_lib.sources.archive:
CryptoVenuePlugin, a crypto exchange's; liminal-lib 1.3.0: what it declares class attributes, what
it does methods), registered under the entry point group `liminal.providers` as `bitstamp`. It relies
on nothing of the app outside the contract (docs/ARCHITECTURE.md in liminal-app: "Providers are
plugins"); its version is this distribution's (pyproject.toml), so PLUGIN.version is left empty.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Iterator

from liminal_lib.config import Tier
from liminal_lib.freshness import Delay
from liminal_lib.models import Instrument
from liminal_lib.sources.archive import EXCHANGE_FRAMES, Archive as _Archive, bounds as _bounds
from liminal_lib.sources.archive import CryptoVenuePlugin
from liminal_lib.sources.registry import FeedPlugin
from liminal_lib.sources.stream import Live, Reconnect, trade

BASE_URL = "https://www.bitstamp.net/api/v2"
# Its plan and caps (once the app's config.PUBLIC_FEEDS["bitstamp"]): Bitstamp allows 8,000 requests
# per 10 minutes; well inside it.
TIER = Tier("bitstamp-public", requests_per_minute=300, history_years=None, history_start=date(2011, 8, 1))
PER_RUN, PER_DAY = 8000, 20000

BITSTAMP_PAIRS = {"BTCUSD", "BTCEUR", "ETHUSD", "ETHEUR", "ETHBTC", "LTCUSD", "XRPUSD", "BCHUSD", "LINKUSD",
                  "SOLUSD", "ADAUSD", "DOGEUSD", "AVAXUSD", "DOTUSD", "XLMUSD", "UNIUSD", "USDCUSD", "USDTUSD"}
BITSTAMP_STEPS = {("minute", 1): 60, ("minute", 5): 300, ("hour", 1): 3600, ("day", 1): 86400}


class BitstampSource(_Archive):
    name = "bitstamp"
    assets = ("crypto",)
    archival = False  # an exchange: its own market, still trading
    PAGE = 1000  # bars per request (the API's maximum)

    def resolutions(self, asset: str) -> tuple[str, ...]:
        return ("minute",) if asset == "crypto" else ()

    def native_frames(self, asset: str) -> tuple[tuple[str, int], ...]:
        return EXCHANGE_FRAMES if asset == "crypto" else ()

    def covers(self, ticker: str) -> bool:
        return ticker.upper().removeprefix("X:") in BITSTAMP_PAIRS

    def bar_pages(self, ticker, start, end, timespan, multiplier=1, descending=False, asset="crypto",
                  limit: int | None = None) -> Iterator[list[dict]]:
        if (timespan, multiplier) not in BITSTAMP_STEPS:
            raise ValueError(f"Bitstamp steps: {tuple(BITSTAMP_STEPS)}")
        pair = ticker.upper().removeprefix("X:").lower()
        step = BITSTAMP_STEPS[(timespan, multiplier)]
        a, b = _bounds(start, end)
        a_s, b_s = -(-a // 1000), b // 1000
        cursor = b_s - step if descending else a_s
        while (cursor >= a_s) if descending else (cursor < b_s):
            params = {"step": step, "limit": limit or self.PAGE}
            params.update({"end": cursor} if descending else {"start": cursor})
            rows = (self.client.get(f"/ohlc/{pair}/", params).get("data") or {}).get("ohlc") or []
            stamps = [int(r["timestamp"]) for r in rows]
            bars = [{"t": ts * 1000, "o": float(r["open"]), "h": float(r["high"]), "l": float(r["low"]),
                     "c": float(r["close"]), "v": float(r["volume"]), "vw": None, "n": None}
                    for ts, r in zip(stamps, rows) if a_s <= ts < b_s and float(r["volume"]) > 0]
            yield sorted(bars, key=lambda x: -x["t"]) if descending else bars
            if not stamps or limit:
                return
            nxt = min(stamps) - step if descending else max(stamps) + step
            if (descending and nxt >= cursor) or (not descending and nxt <= cursor):
                return  # no progress: the start of the pair's history
            cursor = nxt

    def instrument(self, ticker: str, resolve_exchange: bool = True) -> Instrument:
        pair = ticker.upper().removeprefix("X:")
        return Instrument(ticker=pair, name=f"{pair[:-3]}/{pair[-3:]} on Bitstamp", details={"venue": "Bitstamp"})


@dataclass
class BitstampStream:
    """Bitstamp's public v2 feed: a live_trades channel per pair."""
    source: str = "bitstamp"
    url: str = "wss://ws.bitstamp.net"
    keepalive: str | None = json.dumps({"event": "bts:heartbeat"})
    dynamic: bool = False  # as Coinbase's stream
    asset: str = "crypto"
    authed: bool = True
    confirmed: frozenset = frozenset()

    def subscribe(self, coins) -> list[str]:
        self.confirmed = frozenset()
        return [json.dumps({"event": "bts:subscribe", "data": {"channel": f"live_trades_{c.lower()}usd"}})
                for c in coins]

    def change(self, add, drop) -> list[str]:
        return [json.dumps({"event": f"bts:{kind}", "data": {"channel": f"live_trades_{t.lower()}"}})
                for kind, pairs in (("unsubscribe", drop), ("subscribe", add)) for t in sorted(pairs)]

    def parse(self, msg: dict) -> list[tuple[str, dict]]:
        event = msg.get("event")
        if event == "bts:request_reconnect":
            raise Reconnect("bitstamp asked for a new connection")
        if event == "bts:error":
            data = msg.get("data") if isinstance(msg.get("data"), dict) else {}
            raise ConnectionError(f"bitstamp: {data.get('message') or msg}")
        if event in ("bts:subscription_succeeded", "bts:unsubscription_succeeded"):
            pair = str(msg.get("channel") or "").removeprefix("live_trades_").upper()
            self.confirmed = (self.confirmed | {pair}) if event == "bts:subscription_succeeded" else (self.confirmed - {pair})
            return []
        if event != "trade":
            return []
        d = msg["data"]
        ticker = msg["channel"].removeprefix("live_trades_").upper()
        tid = int(d["id"])
        return [(ticker, trade(int(d["microtimestamp"]) * 1000, tid, d.get("price_str", d["price"]),
                                d.get("amount_str", d["amount"]), tid))]


class BitstampPlugin(CryptoVenuePlugin):
    """The feed's plugin, a crypto exchange's (its `assets` and `kind`; its source on the contract's
    public client at `base_url`): what it declares as attributes, what it does as methods (the pairs
    it carries); the contract's defaults for the rest. Its view is the contract's own, as its record's
    was: its fixed plan and caps, all the history it holds, CRYPTO_VENUE_DAYS not applied (the app
    limits Coinbase and Bitfinex with it)."""

    api = "2.0"  # the contract it is written for (the class contract); its version: the distribution's
    name = "bitstamp"
    title = "Bitstamp"
    about = "crypto minute bars from 2011 (no key)"
    order = 20
    base_url = BASE_URL
    source_class = BitstampSource
    tier = TIER
    per_run = PER_RUN
    per_day = PER_DAY
    limits = "8,000 requests per 10 minutes"
    per_request = {"day": BitstampSource.PAGE, "minute": BitstampSource.PAGE}
    streams = {"crypto": "real time, public trades (no key), coins open on a chart"}
    live = (Live("bitstamp", "crypto", stream=BitstampStream),)
    # when its data is published (the library's freshness row for its plan): each minute once it closes
    delays = {"bitstamp-public": {"crypto": Delay("delay")}}

    def view(self, base):
        """The contract's default (FeedPlugin.view): its fixed tier and caps, the history unlimited."""
        return FeedPlugin.view(self, base)

    def carries(self, spec):
        return spec.ticker.upper() in BITSTAMP_PAIRS


PLUGIN = BitstampPlugin()
