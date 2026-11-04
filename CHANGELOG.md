# Changelog

## 0.2.0 (2026-11-03)

- A class on plugin API 2.0 (liminal-lib 1.3.0; the user: "all the plugins under liminal should basically
  follow inheritance/oop paradigm"): `BitstampPlugin(CryptoVenuePlugin)`, a crypto exchange's plugin of
  `liminal_lib.sources.archive` (its `assets` and `kind`; its source built on the contract's public client at
  `base_url`), what the `Provider` record declared as class attributes and its callback as a method
  (`carries`), `PLUGIN` its instance. Its `view` stays the contract's own, as the record's was: its fixed
  plan and caps, all the history it holds (`CRYPTO_VENUE_DAYS` limits Coinbase and Bitfinex, not it).
- It declares its publication delay itself (`delays`: each minute once it closes, the row the library held
  for the `bitstamp-public` plan).
- Every behaviour, limit and string as in 1.3.1. Versioned 0.2.0 with every Liminal distribution of the
  release (its `release/0.2.0` branch; CI against the library's).

## 1.3.1 (2026-11-02)

The plugin imports the library as `liminal_lib` and depends on liminal-lib (the app, renamed liminal-app, is no longer needed to run the tests; the user, 2026-11-02: "lets rename the app to liminal-app").

## 1.3.0 (2026-11-01)

- Released as its own package, `liminal-plugin-bitstamp`, registered under the entry point group
  `liminal.providers`; its version is the distribution's.
- Its plan and request caps are in it (`TIER`, `PER_RUN`, `PER_DAY`), no longer in the app's
  `config.PUBLIC_FEEDS`.
- Plugin API 1.6.

## 1.2.0 (2026-10-31)

- Built into the app (then massive-collate): its source class, client and trade stream in its
  module (plugin API 1.6).

## 1.1.0 and 1.0.0

- Built into the app (then massive-collate); see the app's history.
