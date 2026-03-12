"""SimTrader broker simulation: fill engine, latency model, order management.

Public surface::

    from packages.polymarket.simtrader.broker.latency import LatencyConfig, ZERO_LATENCY
    from packages.polymarket.simtrader.broker.rules import Order, FillRecord, Side, OrderStatus
    from packages.polymarket.simtrader.broker.fill_engine import try_fill
    from packages.polymarket.simtrader.broker.sim_broker import SimBroker
"""
