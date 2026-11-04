"""The Bitstamp plugin, run against the app installed beside it: its candle pages and its trade
stream's messages, and the app loading it from this package with its own version and the facts it
had as a built-in."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib.metadata import version

import pytest

from liminal_lib import composite, freshness
from liminal_lib.config import load_settings
from liminal_lib.freshness import Delay
from liminal_lib.sources import is_archive, markets, provider, registry, supports
from liminal_lib.sources.archive import CryptoVenuePlugin
from liminal_lib.sources.http import PublicClient
from liminal_lib.sources.stream import Reconnect
from liminal_lib.symbols import resolve

import liminal_plugin_bitstamp
from liminal_plugin_bitstamp import BASE_URL, PER_DAY, PER_RUN, TIER, BitstampPlugin, BitstampSource, BitstampStream

from .conftest import FakeResponse, FakeSession


def _client(responses):
    session = FakeSession(responses)
    return PublicClient("https://x.test/api", session=session, sleep=lambda s: None), session


def _ohlc(ts, v="1.0"):
    return {"timestamp": str(ts), "open": "10", "high": "11", "low": "9", "close": "10.5", "volume": v}


def test_bitstamp_pages_newest_first_and_drops_empty_minutes():
    t0 = int(datetime(2015, 1, 1, tzinfo=timezone.utc).timestamp())
    page1 = {"data": {"ohlc": [_ohlc(t0 + 60 * i, "0.0" if i % 2 else "2.0") for i in range(5, 10)]}}
    page2 = {"data": {"ohlc": [_ohlc(t0 + 60 * i) for i in range(0, 5)]}}
    client, session = _client([FakeResponse(200, page1), FakeResponse(200, page2), FakeResponse(200, page2)])
    src = BitstampSource(client)
    src.PAGE = 5
    pages = list(src.bar_pages("X:BTCUSD", datetime.fromtimestamp(t0, timezone.utc),
                               datetime.fromtimestamp(t0 + 600, timezone.utc), "minute", descending=True))
    assert [b["t"] // 1000 - t0 for b in pages[0]] == [480, 360]  # zero-volume minutes dropped, newest first
    assert len(pages[1]) == 5
    url, params, headers = session.calls[0]
    assert url.endswith("/ohlc/btcusd/") and params == {"step": 60, "limit": 5, "end": t0 + 540}
    assert session.calls[1][1]["end"] == t0 + 240 and "liminal" in headers["User-Agent"]
    assert len(session.calls) == 2  # stops once a page reaches the window's start


def test_it_sends_five_minute_and_hourly_candles_and_refuses_other_steps():
    t0 = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())
    lo, hi = datetime.fromtimestamp(t0, timezone.utc), datetime.fromtimestamp(t0 + 3600, timezone.utc)
    client, session = _client([FakeResponse(200, {"data": {"ohlc": [_ohlc(t0)]}}), FakeResponse(200, {"data": {"ohlc": []}})])
    list(BitstampSource(client).bar_pages("X:BTCUSD", lo, hi, "minute", 5))
    assert session.calls[0][1]["step"] == 300
    assert BitstampSource(client).native_frames("crypto") == (("minute", 5), ("hour", 1))
    with pytest.raises(ValueError):
        list(BitstampSource(client).bar_pages("X:BTCUSD", lo, hi, "minute", 3))  # not a Bitstamp step
    inst = BitstampSource(client).instrument("X:ETHUSD")
    assert inst.ticker == "ETHUSD" and inst.details["venue"] == "Bitstamp"


def test_its_stream_messages_become_trades_and_its_subscriptions_are_confirmed():
    s = BitstampStream()
    bs = s.parse({"event": "trade", "channel": "live_trades_btcusd", "data": {
        "id": 9, "microtimestamp": "1792825200123456", "price": 81000, "price_str": "81000.5", "amount": 0.1,
        "amount_str": "0.1"}})
    assert bs[0][0] == "BTCUSD" and bs[0][1]["sip_timestamp"] == 1_792_825_200_123_456_000 and bs[0][1]["price"] == 81000.5
    assert s.parse({"event": "bts:heartbeat"}) == []
    with pytest.raises(Reconnect):
        s.parse({"event": "bts:request_reconnect"})
    with pytest.raises(ConnectionError):
        s.parse({"event": "bts:error", "data": {"message": "Bad subscription"}})
    subs = [json.loads(m) for m in s.subscribe(("BTC", "ETH"))]
    assert [x["data"]["channel"] for x in subs] == ["live_trades_btcusd", "live_trades_ethusd"]
    s.parse({"event": "bts:subscription_succeeded", "channel": "live_trades_ethusd", "data": {}})
    s.parse({"event": "bts:subscription_succeeded", "channel": "live_trades_btcusd", "data": {}})
    s.parse({"event": "bts:unsubscription_succeeded", "channel": "live_trades_btcusd", "data": {}})
    assert s.confirmed == {"ETHUSD"}
    changes = [json.loads(m) for m in s.change(add={"SOLUSD"}, drop={"ETHUSD"})]
    assert [(c["event"], c["data"]["channel"]) for c in changes] == [
        ("bts:unsubscribe", "live_trades_ethusd"), ("bts:subscribe", "live_trades_solusd")]


def test_the_app_loads_it_from_this_package_with_its_own_version():
    registry.reload()
    p = provider("bitstamp")
    assert p is not None, dict(registry.errors())
    assert p.origin in {"package: liminal-plugin-bitstamp (liminal_plugin_bitstamp:PLUGIN)", "plugins/liminal-plugin-bitstamp (liminal_plugin_bitstamp:PLUGIN)"}  # its package, or its checkout in the workspace\'s plugin directory
    assert p.version == version("liminal-plugin-bitstamp") and liminal_plugin_bitstamp.PLUGIN.version == ""
    assert registry.api_refusal(p.api) is None
    assert not [why for where, why in registry.errors() if "bitstamp" in where or "bitstamp" in why]
    row = {r["name"]: r for r in registry.menu()}["bitstamp"]
    assert (row["version"], row["api"]) == (version("liminal-plugin-bitstamp"), "2.0")


def test_it_keeps_the_facts_it_had_built_in():
    registry.reload()
    s = load_settings(env={}, env_file=None)
    view = s.for_source("bitstamp")
    assert (view.tier, view.max_requests_per_run, view.max_requests_per_day) == (TIER, PER_RUN, PER_DAY)
    assert load_settings(env={"CRYPTO_VENUE_DAYS": "30"}, env_file=None).for_source("bitstamp").tier.history_days is None
    assert not is_archive("bitstamp") and markets("bitstamp", s) == {"crypto": "bitstamp"}
    assert supports("bitstamp", resolve("BTCUSD")) and not supports("bitstamp", resolve("AAPL"))
    assert composite.feed_kind("bitstamp", "crypto") == "exchange"
    p = provider("bitstamp")
    assert [(f.name, f.asset, f.stream) for f in p.live] == [("bitstamp", "crypto", BitstampStream)]


def test_it_is_a_class_on_the_contract_and_the_app_loads_it_as_one():
    p = liminal_plugin_bitstamp.PLUGIN
    assert isinstance(p, BitstampPlugin) and isinstance(p, CryptoVenuePlugin) and p.api == "2.0" and not p.is_record
    assert p.assets == frozenset({"crypto"}) and p.kind == "exchange"  # a crypto venue's, from its base
    assert p.gives("build") and p.gives("view") and p.gives("carries")
    assert not p.has_scan and not p.has_settings and not p.gives("rate") and not p.gives("markets")
    assert p.delays == {"bitstamp-public": {"crypto": Delay("delay")}} and p.hours == {}
    loaded = registry.reload()["bitstamp"]
    assert type(loaded) is BitstampPlugin and (loaded.version, loaded.api) == (version("liminal-plugin-bitstamp"), "2.0")
    assert not [why for where, why in registry.errors() if "bitstamp" in where or "bitstamp" in why]
    src = loaded.build(load_settings(env={}, env_file=None), 5)  # its base's build: its source on the public client
    assert isinstance(src, BitstampSource) and isinstance(src.client, PublicClient) and src.client.base_url == BASE_URL
    assert freshness.plan_delay(TIER, "crypto").kind == "delay"  # its own rule (BitstampPlugin.delays; the library's too)
    moved = p.with_(order=1)  # a changed copy (the registry's version and origin come this way)
    assert type(moved) is BitstampPlugin and moved.order == 1 and p.order == 20
