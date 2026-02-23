"""SimTrader portfolio: cash, positions, realized/unrealized PnL.

Modules:
  fees.py   — Decimal-safe fee computation (conservative default)
  mark.py   — Mark price for unrealized PnL (bid-side or midpoint)
  ledger.py — PortfolioLedger: consumes broker events, emits balance snapshots
"""
