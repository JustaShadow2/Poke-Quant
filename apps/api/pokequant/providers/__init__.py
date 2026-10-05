"""Data-source provider adapters behind typed ports.

Every external source (PokemonTCG.io, eBay Browse, FRED, ...) implements a small
Protocol so the ingestion pipeline is source-agnostic and each adapter is
unit-testable against recorded fixtures (docs/adr/0006-provider-plugin-interface.md).
"""
