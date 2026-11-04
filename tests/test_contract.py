"""Every plugin here conforms to the class contract (plugin API 2.0): liminal_libs.sources.conformance,
read from the plugin alone (nothing is sent). The user, 2026-11-03: "evaluate each functional piece
of software or plugin and verify correctness and valid functionality through unit tests created to
address new class scheme"."""
from __future__ import annotations

import plugin_integrator_bitstamp as module
from liminal_libs.sources.conformance import assert_module_conforms


def test_every_plugin_here_conforms_to_the_class_contract():
    found = assert_module_conforms(module)
    assert found and all(p.api == "2.0" and not p.is_record for p in found)  # classes, written for 2.0
    assert {p.SYSTEM for p in found} == {"integrator"}  # the system it plugs into, by its name
