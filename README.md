# liminal-plugin-bitstamp

Bitstamp for [Liminal](https://github.com/pcxmac-dev/liminal-app): the exchange's crypto minute bars
from 2011 (its public candles API) and its public trade stream, for the coins open on a chart. No
key. An exchange of its own: its history is a market apart from the other exchanges', never closed.

A Liminal provider plugin released on its own. The app finds it through the entry point group
`liminal.providers` and lists it on the Plugins view and in `liminal plugins`
as `package: liminal-plugin-bitstamp`, with this package's version.

## Install

Into the app's environment, from the app's folder:

```powershell
.venv\Scripts\python.exe -m pip install "liminal-plugin-bitstamp @ git+https://github.com/pcxmac-dev/liminal-plugin-bitstamp@v0.2.0"
```

or with the app's plugins (`pip install -e ".[plugins]"` in liminal-app). The app loads it on its next
start.

## Compatibility

It is written for plugin API 2.0 (`PLUGIN.api`: the class contract, `BitstampPlugin` a
`CryptoVenuePlugin` of liminal-lib 1.3.0 or later). An app offering 2.0 or a later 2.x loads it; an
app of another major, or one older than 2.0, leaves it out and says why on the Plugins view.

## Develop

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install "liminal-lib @ git+https://github.com/pcxmac-dev/liminal-lib@main"
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest -q
```

Tests never send requests (a fake session answers) and never read your keys.
