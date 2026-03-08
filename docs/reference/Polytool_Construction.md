# POLYTOOL

## From Research Pipeline to Profitable Live Bot

_The Complete Engineering & Strategy Construction Manual_

```
Roadmaps 0–5 Complete · SimTrader MVPs 1–
Complete
Next: Live Execution + Alpha Factory
March 2026 · Confidential
```

## 0. Start Here — Answer to Your Question

**Q: Which should I work on first — SimTrader execution or the Alpha Factory?**

###### TRACK A TRACK B

```
SimTrader → Execution → Live Bot
Start TODAY. This is the critical path.
Week 1: LiveExecutor + RiskManager
Week 2: MarketMakerStrategy + shadow run
Week 3: Market selection + dry-run live
Week 4–5: $500 live deployment
Revenue starts here. Real feedback starts
here.
```

```
Wallet Scan → Alpha Discovery →
Strategies
Start SAME DAY. Runs in parallel.
Week 1–2: wallet-scan on top performers
Week 2–3: batch-run, alpha-distill v
Week 3–5: news ingest + signals layer
Week 6+: discovered strategies go live
This is the alpha engine that beats everyone
long-term.
```

```
Convergence at Week 6: Track A gives you a live, running execution layer with real
revenue. Track B gives you the first discovered strategy derived from actual profitable
```

```
wallets. Deploy it into the already-running bot. From here, every new discovered strategy is
a new revenue stream dropped into an infrastructure that already works.
```

```
Short answer: Build the LiveExecutor + MarketMakerStrategy first (Track A). You can have real
orders on Polymarket in 2 weeks. Do NOT wait for the full Alpha Factory. The Alpha Factory is
what transforms a working bot into an unbeatable bot — but you need the bot running first to get
real feedback data.
```

## 1. Current State Inventory

Everything listed below is COMPLETE and working. This is the foundation. Nothing needs to be
rebuilt. The goal from here is to add the execution layer and alpha discovery on top.

##### Research Pipeline — Roadmaps 0–

**Component Status What It Does**

```
ClickHouse Schema + API
Ingest
```

```
COMPL
ETE
```

```
All Polymarket trade/position/market data ingested into
local ClickHouse
```

```
Grafana Dashboards COMPL
ETE
```

```
User Trades, Strategy Detectors, PnL, Arb Feasibility
panels
```

```
scan CLI COMPL
ETE
```

```
One-shot ingestion + trust artifact emission
(coverage_reconciliation_report, run_manifest)
```

```
Strategy Detectors COMPL
ETE
```

```
HOLDING_STYLE, DCA_LADDERING,
MARKET_SELECTION_BIAS,
COMPLETE_SET_ARBISH
```

```
PnL Computation COMPL
ETE
```

```
FIFO realized + MTM. Fee model: 2% on gross profit
(SPEC-0004)
```

```
Resolution Enrichment (R3) COMPL
ETE
```

```
4-stage chain: ClickHouse → OnChainCTF (Polygon
RPC) → Subgraph → Gamma.
UNKNOWN_RESOLUTION < 5%
```

```
Segment Analysis (R4) COMPL
ETE
```

```
Breakdown by entry_price_tier, market_type, category,
league, sport
```

```
CLV Capture (R5) COMPL
ETE
```

```
Closing Line Value per position: closing_price −
entry_price. Cache-first enrichment.
```

**Component Status What It Does**

```
batch-run + Hypothesis
Leaderboard (R5.5)
```

```
COMPL
ETE
```

```
Multi-user batch scan. Notional-weighted CLV
aggregation. Deterministic leaderboard.
```

```
Local RAG (R1) COMPL
ETE
```

```
Chroma vector + FTS5 lexical + RRF hybrid +
cross-encoder rerank. Fully offline.
```

```
LLM Bundle + Save (R1) COMPL
ETE
```

```
Evidence bundles, prompt templates, structured
hypothesis.json output (schema v1)
```

```
export-dossier (R1) COMPL
ETE
```

```
memo.md + dossier.json + manifest.json per user.
WIN/LOSS/PROFIT_EXIT/LOSS_EXIT taxonomy.
```

##### SimTrader — MVPs 1–

**MVP Status Capability**

```
MVP1: Tape
Recorder
```

```
COMPL
ETE
```

```
WS Market Channel → deterministic events.jsonl tapes. Captures all
book updates, trades, fills.
```

```
MVP2: L2 Book
Reconstruction
```

```
COMPL
ETE
```

```
Replay events.jsonl → reconstructed L2 orderbook state at any point in
time.
```

```
MVP3: Replay
Runner +
BrokerSim
```

```
COMPL
ETE
```

```
Strategy receives book events → places simulated orders →
BrokerSim fills with realistic queue position model.
```

```
MVP4: Sweeps
+ Studio
```

```
COMPL
ETE
```

```
Parameter grid sweeps across any strategy config. Local HTML report.
simtrader batch leaderboard.
```

```
MVP5: Shadow
Mode
```

```
COMPL
ETE
```

```
Live WS → strategy decisions → BrokerSim fills (no real orders).
Same artifact schema as replay.
```

```
Strategies:
complement_arb
```

```
COMPL
ETE
```

```
Binary arb detector. YES+NO best_ask < 1.0 − fees triggers dual-leg
attempt.
```

```
Strategies:
copy_wallet_repl
ay
```

```
COMPL
ETE
```

```
Replays a target wallet trades against public book to measure
execution edge.
```

```
Fault Injection COMPL
ETE
```

```
delayed_fill, partial_fill, missed_fill, gap_injection, stale_book faults for
stress testing.
```

##### The Exact Gap — What Is Missing

```
Critical Gap: SimTrader has no live order execution. All fills are simulated. There is no
LiveExecutor, no connection to py-clob-client, no RiskManager enforcing pre-trade limits, and no
kill switch. This is the only thing standing between the current system and a live trading bot.
```

```
Secondary Gap: The research pipeline targets individual users manually. There is no
wallet-scan command to auto-discover top performers at scale, no alpha-distill to automatically
extract strategy patterns from batch data, and no Research RAG to store only validated,
high-trust findings.
```

```
What this document delivers: Complete engineering specifications for both gaps — the
execution layer (Track A, start now) and the alpha discovery factory (Track B, run in parallel).
Every component is specified at implementation level.
```

## 2. Track A — SimTrader Execution Layer

## (Start Now)

Build order: executor.py → wallet.py → risk.py → kill_switch.py → live_runner.py. Every
component has a clear interface so they can be built and tested independently.

##### 2.1 Package Structure

```
packages/polymarket/simtrader/
execution/ ← NEW PACKAGE
__init__.py
executor.py ← LiveExecutor: wraps py-clob-client
wallet.py ← Wallet + API credential management
risk.py ← RiskManager: pre-trade checks
kill_switch.py ← File-based kill switch
live_runner.py ← LiveRunner: extends ShadowRunner
models.py ← Order, Fill, Position dataclasses
strategies/
market_maker.py ← MarketMakerStrategy (NEW)
complement_arb.py ← (existing)
copy_wallet_replay.py ← (existing)
generated/ ← Auto-generated from StrategySpec (later)
tests/
test_executor.py
test_risk.py
test_live_runner_dry_run.py
```

##### 2.2 executor.py — LiveExecutor

The execution primitive. Wraps py-clob-client. All order placement goes through here. Rate-limit
aware. Never places market orders.

# packages/polymarket/simtrader/execution/executor.py

import asyncio
import time
from collections import deque
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType,
PartialCreateOrderOptions
from .models import Order, Fill, OrderSide

class LiveExecutor:
"""
Thin async wrapper around py-clob-client.
Rate limit: 60 orders/min per Polymarket API docs.
All methods are async and safe to call from the event loop.
"""
RATE_LIMIT_PER_MIN = 55 # conservative (55, not 60)
WINDOW_SECONDS = 60.

def **init**(self, client: ClobClient, dry_run: bool = False):
self.client = client
self.dry_run = dry_run # if True: log but never send
self.\_ts_q = deque() # timestamps of recent orders
self.\_lock = asyncio.Lock()

async def \_rate_check(self):
"""Block until we are under the rate limit."""
now = time.monotonic()

# purge old timestamps

while self.\_ts_q and now - self.\_ts_q[0] >= self.WINDOW_SECONDS:
self.\_ts_q.popleft()
if len(self.\_ts_q) >= self.RATE_LIMIT_PER_MIN:
sleep_for = self.WINDOW_SECONDS - (now - self.\_ts_q[0]) + 0.
await asyncio.sleep(sleep_for)
self.\_ts_q.append(time.monotonic())

async def place*limit_order(self, token_id: str, side: OrderSide,
price: float, size: float) -> dict | None:
"""Place a GTC limit order. Returns order dict or None on dry-run."""
async with self.\_lock:
await self.\_rate_check()
if self.dry_run:
print(f"[DRY-RUN] LIMIT {side.value} {size} @ {price:.4f}
token={token_id[:8]}")
return {"id": f"dry*{token*id[:8]}*{price:.4f}", "status": "dry_run"}
order_args = OrderArgs(
token_id = token_id,
price = price,
size = size,
side = side.value, # "BUY" or "SELL"
order_type = OrderType.GTC,
)
return self.client.create_order(order_args)

```
async def cancel_order(self, order_id: str) -> bool:
async with self._lock:
await self._rate_check()
if self.dry_run:
print(f"[DRY-RUN] CANCEL order_id={order_id}")
return True
resp = self.client.cancel(order_id)
return resp.get("canceled", False)
```

```
async def cancel_all(self) -> int:
"""Emergency cancel-all. Bypasses rate limit check — safety first."""
if self.dry_run:
print("[DRY-RUN] CANCEL ALL")
return 0
resp = self.client.cancel_all()
return len(resp.get("canceled", []))
```

```
async def get_open_orders(self) -> list[dict]:
return self.client.get_orders() or []
```

```
async def get_position(self, token_id: str) -> float:
"""Returns current balance of token_id from wallet."""
positions = self.client.get_positions() or []
for p in positions:
if p.get("asset_id") == token_id:
return float(p.get("size", 0))
return 0.
```

##### 2.3 wallet.py — Credential Management

Loads private key from environment. Derives API credentials via py-clob-client. Handles the
one-time USDC allowance setup. Never stores secrets in code.

# packages/polymarket/simtrader/execution/wallet.py

```
import os
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
```

```
POLYGON_RPC = os.environ.get("POLYGON_RPC", "https://polygon-rpc.com")
CLOB_HOST = "https://clob.polymarket.com"
CHAIN_ID = POLYGON # 137
```

```
def build_client() -> ClobClient:
"""
Build an authenticated ClobClient.
Requires env vars:
PK - hex private key of trading wallet (no 0x prefix)
CLOB_API_KEY - from derive_api_creds() or Polymarket dashboard
CLOB_API_SECRET - same
CLOB_API_PASSPHRASE - same
```

```
Run derive_creds.py once to generate and save these.
"""
pk = os.environ["PK"]
return ClobClient(
host = CLOB_HOST,
chain_id = CHAIN_ID,
key = pk,
signature_type = 0, # EOA wallet; use 1 for Magic/proxy wallets
)
```

```
def derive_and_print_creds(client: ClobClient):
"""One-time setup: derive API credentials and print for .env storage."""
creds = client.derive_api_key()
print(f"CLOB_API_KEY={creds['apiKey']}")
print(f"CLOB_API_SECRET={creds['secret']}")
print(f"CLOB_API_PASSPHRASE={creds['passphrase']}")
```

##### 2.4 risk.py — RiskManager

Every order goes through the RiskManager before being sent to the LiveExecutor. Violations
trigger cancel-all and halt. This is the last line of defense.

# packages/polymarket/simtrader/execution/risk.py

```
from dataclasses import dataclass
from .models import Order, OrderSide
```

```
@dataclass
class RiskConfig:
max_position_per_market_usdc : float = 500.0 # max USDC long/short per
token
max_total_notional_usdc : float = 4000.0 # max total exposure across
all markets
max_order_size_usdc : float = 200.0 # single order size cap
daily_loss_cap_usdc : float = 100.0 # stop if realized PnL < -
today
inventory_skew_limit_usdc : float = 400.0 # max abs(long - short)
inventory
```

```
class RiskManager:
def __init__(self, config: RiskConfig):
self.cfg = config
self.positions = {} # token_id -> net_position (+ = long, - =
short)
self.daily_pnl = 0.0 # updated on fills
```

```
def check_order(self, order: Order, current_usdc_balance: float) ->
tuple[bool, str]:
"""
Returns (approved: bool, reason: str).
Call this BEFORE sending to LiveExecutor.
```

```
"""
size_usdc = order.price * order.size
```

```
# 1. Single order size cap
if size_usdc > self.cfg.max_order_size_usdc:
return False, f"order_too_large: {size_usdc:.2f} >
{self.cfg.max_order_size_usdc}"
```

```
# 2. Market-level position cap
current_pos = self.positions.get(order.token_id, 0.0)
delta = order.size if order.side == OrderSide.BUY else -order.size
new_pos_usdc = abs((current_pos + delta) * order.price)
if new_pos_usdc > self.cfg.max_position_per_market_usdc:
return False, f"position_cap: {new_pos_usdc:.2f} >
{self.cfg.max_position_per_market_usdc}"
```

```
# 3. Total notional cap
total = sum(abs(v) for v in self.positions.values()) * order.price
if total + size_usdc > self.cfg.max_total_notional_usdc:
return False, f"notional_cap: {(total+size_usdc):.2f} >
{self.cfg.max_total_notional_usdc}"
```

```
# 4. Daily loss cap
if self.daily_pnl < -self.cfg.daily_loss_cap_usdc:
return False, f"daily_loss_cap: pnl={self.daily_pnl:.2f}"
```

return True, "approved"

```
def on_fill(self, token_id: str, side: OrderSide, size: float, price: float,
realized_pnl: float = 0.0):
delta = size if side == OrderSide.BUY else -size
self.positions[token_id] = self.positions.get(token_id, 0.0) + delta
self.daily_pnl += realized_pnl
```

##### 2.5 kill_switch.py — Emergency Stop

File-based. If the file KILL exists in the artifacts directory, all operations halt immediately. Can be
triggered from another terminal, a monitoring script, or manually. Zero dependencies.

```
# packages/polymarket/simtrader/execution/kill_switch.py
import os
from pathlib import Path
```

KILL_FILE_PATH = Path("artifacts/simtrader/KILL")

```
def is_killed() -> bool:
return KILL_FILE_PATH.exists()
```

```
def arm_kill_switch():
KILL_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
KILL_FILE_PATH.touch()
```

print(f"[KILL SWITCH] Armed: {KILL_FILE_PATH}")

```
def disarm_kill_switch():
if KILL_FILE_PATH.exists():
KILL_FILE_PATH.unlink()
print(f"[KILL SWITCH] Disarmed: {KILL_FILE_PATH}")
```

```
def check_or_raise():
if is_killed():
raise RuntimeError(f"KILL SWITCH ACTIVE — halt. Remove {KILL_FILE_PATH} to
resume.")
```

##### 2.6 live_runner.py — LiveRunner

Extends ShadowRunner. Replaces simulated BrokerSim fills with real LiveExecutor calls.
Maintains identical artifact output schema so all existing Grafana dashboards and report tooling
continue to work.

# packages/polymarket/simtrader/execution/live_runner.py

```
import asyncio
from ..shadow_runner import ShadowRunner # existing
from .executor import LiveExecutor
from .risk import RiskManager
from .kill_switch import check_or_raise
from .models import Order
```

```
class LiveRunner(ShadowRunner):
"""
Drop-in replacement for ShadowRunner that executes real orders.
--dry-run flag keeps LiveExecutor in dry_run=True mode for final
validation before committing real capital.
"""
def __init__(self, executor: LiveExecutor, risk: RiskManager, **kwargs):
super().__init__(**kwargs)
self.executor = executor
self.risk = risk
self._open_orders: dict[str, dict] = {} # order_id -> order info
```

```
async def _place_order(self, order: Order):
"""Override: send order through risk check → executor."""
check_or_raise() # kill switch first
usdc_balance = await self._get_usdc_balance()
approved, reason = self.risk.check_order(order, usdc_balance)
if not approved:
self._log_rejection(order, reason)
return None
result = await self.executor.place_limit_order(
order.token_id, order.side, order.price, order.size
)
if result:
```

```
self._open_orders[result["id"]] = order
return result
```

```
async def _cancel_order(self, order_id: str):
check_or_raise()
await self.executor.cancel_order(order_id)
self._open_orders.pop(order_id, None)
```

```
async def emergency_stop(self):
"""Cancel all open orders immediately. Call on WS stall or kill switch."""
count = await self.executor.cancel_all()
self._open_orders.clear()
print(f"[EMERGENCY STOP] Cancelled {count} open orders")
```

```
async def _get_usdc_balance(self) -> float:
# Query USDC balance from CLOB positions
positions = await asyncio.to_thread(self.executor.client.get_balance)
return float(positions or 0)
```

##### 2.7 CLI Integration

```
# Run with dry-run (no real orders, all validation active)
python -m polytool simtrader live \
--asset-id <TOKEN_ID> \
--strategy market_maker \
--dry-run
```

```
# Run live with real orders
python -m polytool simtrader live \
--asset-id <TOKEN_ID> \
--strategy market_maker \
--live \
--max-position 500 \
--daily-loss-cap 100
```

```
# Emergency stop from separate terminal
touch artifacts/simtrader/KILL
```

##### 2.8 Dependency: py-clob-client

**Requirement Detail**

Package pip install py-clob-client (official Polymarket Python SDK)

Signing EIP-712 signatures handled by the SDK. Private key in env var PK.

```
Order types GTC limit orders only. Never market orders. Never IOC unless explicitly
validated.
```

**Requirement Detail**

```
Gasless trading Builder Program relayer eliminates per-trade gas after one-time USDC approval
(~$0.50 setup cost).
```

```
Polygon RPC Use Chainstack or Alchemy dedicated node ($50–100/month). Public nodes
throttle and drop connections.
```

```
API credentials Derived once from private key using client.derive_api_key(). Store in .env.
Never commit.
```

## 3. Track A — Market Making Strategy

## (Revenue Base)

Market making is the revenue foundation the bot runs on from day one. It works before any
alpha is discovered. The strategy is grounded in the Avellaneda-Stoikov (2008) stochastic
control model, adapted for Polymarket's binary CLOB structure.

##### 3.1 The Avellaneda-Stoikov Model

```
Academic Foundation: Avellaneda, M. & Stoikov, S. (2008). "High-frequency trading in a limit
order book." Quantitative Finance, 8(3), 217–224. This paper established the first rigorous
framework for optimal market making under inventory risk. All spread and reservation price
formulas below derive from this work.
```

**Reservation Price (Inventory-Adjusted Mid)**

A naive market maker quotes symmetrically around the mid-price. The A-S model adjusts the
reference price based on current inventory to control the risk of holding a skewed position:

r = s - q·γ·σ²·(T - t)

```
Where:
r = reservation price (our internal reference, not the market mid)
s = current market mid-price (best_bid + best_ask) / 2
q = current inventory (+ = long YES, - = short/long NO)
γ = risk aversion parameter (0.01–0.5; higher = wider adjustment)
σ² = variance of mid-price over recent window (rolling)
T-t = time remaining in "session" (we use time-to-resolution for binary markets)
```

Interpretation:

```
q > 0 (long YES): r < s → we lower our reference → quotes shift down → more
sells
q < 0 (short YES): r > s → we raise our reference → quotes shift up → more buys
At q = 0: r = s (no skew — symmetric quotes around fair value)
```

**Optimal Spread Formula**

The A-S model also derives the theoretically optimal spread width. Wider spread = more profit
per fill but fewer fills. The optimal spread balances these:

δ_total = γ·σ²·(T-t) + (2/γ)·ln(1 + γ/κ)

```
Where:
δ_total = total bid-ask spread (our quote is r ± δ_total/2)
κ = order book depth factor (higher κ = more liquid book = tighter
spread)
γ, σ², T-t = same as above
```

```
Bid quote: b = r - δ_total/
Ask quote: a = r + δ_total/
```

```
For Polymarket binary markets:
σ is computed from 60-second rolling window of mid-price changes
T-t = hours_to_resolution × 3600 (clamp to 24h max to avoid extreme skewing)
γ = 0.1 (starting value; tune via SimTrader sweep)
κ = estimated from current L2 book depth at best bid/ask
```

**Practical Modifications for Polymarket**

The A-S model assumes continuous-time Brownian motion, which differs from Polymarket's
discrete CLOB and binary resolution structure. Three adaptations are required:

**A-S Assumption Reality on Polymarket Adaptation**

```
Continuous mid-price
process
```

```
Discrete L2 book; mid can
be null in thin markets
```

```
Use size-weighted microprice: Σ(price_i ×
size_i) / Σ(size_i) for top 3 levels
```

```
Infinite trading
session (T→∞
approximation)
```

```
Binary market resolves at
YES=1.0 or NO=0.
```

```
Set T-t = min(hours_to_resolution, 48) in hours.
Clamp to avoid blowup near resolution.
```

```
Symmetric order flow
arrival
```

```
Polymarket has adverse
selection from informed
traders near resolution
```

```
Widen spread multiplicatively when price exits
[0.15, 0.85] range (approaching resolution)
```

##### 3.2 MarketMakerStrategy Implementation

# packages/polymarket/simtrader/strategies/market_maker.py

import math
from collections import deque
from dataclasses import dataclass, field
from ..broker_sim import BookState, Order, OrderSide

@dataclass
class MMConfig:
gamma : float = 0.10 # risk aversion (A-S γ)
kappa : float = 1.50 # order book depth factor (A-S κ)
vol_window_seconds : float = 60.0 # rolling window for σ² estimation
session_hours : float = 24.0 # T parameter (hours)
min_spread : float = 0.020 # floor: never quote tighter than 2¢
max_spread : float = 0.120 # ceiling: never quote wider than 12¢
order_size_usdc : float = 100.0 # size per side (USDC notional)
reprice_threshold : float = 0.005 # reprice when desired differs by > 0.5¢
max_inventory_usdc : float = 400.0 # halt quoting when abs(inventory) > $
resolution_guard : float = 0.10 # widen spread if mid outside [0.10, 0.90]

class MarketMakerStrategy:
"""
Avellaneda-Stoikov market maker for Polymarket binary CLOB.

References:
Avellaneda, M. & Stoikov, S. (2008). Quantitative Finance, 8(3), 217-224.
Guéant, O., Lehalle, C-A., & Fernandez-Tapia, J. (2013).
"Dealing with the inventory risk." Math. and Financial Economics, 7(4).
"""
def **init**(self, cfg: MMConfig, token_id_yes: str, token_id_no: str,
hours_to_resolution: float):
self.cfg = cfg
self.yes_id = token_id_yes
self.no_id = token_id_no
self.T = min(hours_to_resolution, cfg.session_hours)
self.inventory = 0.0 # net YES tokens held (+ = long)
self.bid_id = None # current resting bid order id
self.ask_id = None # current resting ask order id
self.\_mid_history = deque(maxlen=1000) # (ts, mid) for σ² calc
self.\_t_start = None

def _microprice(self, book: BookState) -> float | None:
"""Size-weighted mid from top 3 L2 levels on each side."""
bids = book.bids[:3]
asks = book.asks[:3]
if not bids or not asks:
return None
num = sum(p*s for p,s in bids) + sum(p*s for p,s in asks)
den = sum(s for _,s in bids) + sum(s for \_,s in asks)
return num/den if den > 0 else None

def \_sigma_sq(self, t_now: float) -> float:
"""Rolling variance of mid-price changes."""
cutoff = t_now - self.cfg.vol_window_seconds
pts = [(t,m) for t,m in self._mid_history if t >= cutoff]

if len(pts) < 3:
return 0.0002 # default σ² when insufficient history
changes = [pts[i+1][1] - pts[i][1] for i in range(len(pts)-1)]
mu = sum(changes)/len(changes)
return sum((c-mu)\*\*2 for c in changes)/len(changes)

def \_compute_quotes(self, mid: float, t_elapsed_hours: float,
sigma_sq: float) -> tuple[float, float]:
"""Return (bid_price, ask_price) per A-S model."""
T_t = max(self.T - t_elapsed_hours, 0.01) # avoid zero

# Reservation price (A-S eq. 2.7)

q = self.inventory / (self.cfg.order_size_usdc + 1e-9) # normalized
r = mid - q _ self.cfg.gamma _ sigma_sq \* T_t

# Optimal spread (A-S eq. 2.8)

spread = (self.cfg.gamma _ sigma_sq _ T_t

- (2/self.cfg.gamma) \* math.log(1 +
  self.cfg.gamma/self.cfg.kappa))

# Resolution guard: widen near 0 or 1

if not (self.cfg.resolution_guard < mid < 1-self.cfg.resolution_guard):
spread \*= 2.

spread = max(self.cfg.min_spread, min(self.cfg.max_spread, spread))

bid = round(r - spread/2, 3)
ask = round(r + spread/2, 3)

# Safety: never quote outside [0.01, 0.99]

bid = max(0.01, min(0.98, bid))
ask = max(0.02, min(0.99, ask))
return bid, ask

def on_book_update(self, book: BookState, t_now: float, t_start: float) ->
list:
if self.\_t_start is None:
self.\_t_start = t_start

mid = self.\_microprice(book)
if mid is None:
return []

self.\_mid_history.append((t_now, mid))

# Halt quoting when over inventory limit

inv_usdc = abs(self.inventory) \* mid
if inv_usdc > self.cfg.max_inventory_usdc:
return [{'action':'cancel_all', 'reason':'inventory_limit'}]

t_elapsed = (t_now - self.\_t_start) / 3600.
sigma_sq = self.\_sigma_sq(t_now)
bid, ask = self.\_compute_quotes(mid, t_elapsed, sigma_sq)

```
orders = []
# Only reprice if quotes have moved more than threshold
need_bid = (self.bid_id is None or abs(bid - self._last_bid) >
self.cfg.reprice_threshold)
need_ask = (self.ask_id is None or abs(ask - self._last_ask) >
self.cfg.reprice_threshold)
```

```
if need_bid or need_ask:
if self.bid_id: orders.append({'action':'cancel', 'id':self.bid_id})
if self.ask_id: orders.append({'action':'cancel', 'id':self.ask_id})
size = self.cfg.order_size_usdc / mid
orders.append({'action':'limit', 'side':'BUY', 'price':bid,
'size':size, 'token':self.yes_id})
orders.append({'action':'limit', 'side':'SELL', 'price':ask,
'size':size, 'token':self.yes_id})
self._last_bid = bid
self._last_ask = ask
```

return orders

##### 3.3 Polymarket Liquidity Rewards Integration

**Reward Program Facts:** Polymarket distributed $12.86M across 66,000 addresses in February

2026. Market makers earn rewards proportional to time-weighted liquidity provided within the
      reward spread. New markets (< 48 hours old) yield 80–200% APR equivalent. Two-sided (bid +
      ask) liquidity earns ~3× single-sided. Source: Polymarket Liquidity Rewards documentation,
      Gamma API rewards_config endpoint.

To qualify for rewards, every order must meet three criteria:

- **min_size_cutoff:** Order size must exceed the market's minimum (varies per market; fetch
  from Gamma API gamma-api.polymarket.com/markets/{market_slug}/rewards)
- **max_spread:** Quotes must be within the market's maximum allowed spread. Orders
  outside this spread earn zero rewards.
- **Two-sided:** Post both a bid AND an ask. Single-sided earns ~1/3 of two-sided.

```
# Fetch reward config for a market
import requests
```

```
def get_reward_config(market_slug: str) -> dict:
url = f"https://gamma-api.polymarket.com/markets/{market_slug}/rewards"
resp = requests.get(url, timeout=10)
return resp.json()
# Returns: {"min_size_cutoff": 25.0, "max_spread": 0.08, "reward_rate": 0.003}
```

```
# In MarketMakerStrategy, use reward_config to:
# 1. Ensure order_size_usdc >= min_size_cutoff
# 2. Ensure computed spread <= max_spread (cap it before placing)
```

##### 3.4 Parameter Sweep for Strategy Optimization

Run this sweep on 15+ diverse market tapes before any live deployment. Gate criterion: positive
net PnL (after 2% fee model) on ≥ 70% of tapes.

```
# SimTrader sweep config: market_maker_sweep.yaml
strategy: market_maker
params:
gamma: [0.05, 0.10, 0.20, 0.50]
kappa: [0.80, 1.50, 2.50]
order_size_usdc: [50, 100, 200]
min_spread: [0.010, 0.020, 0.030]
vol_window_seconds: [30, 60, 120]
```

```
# Run against 3 tape categories:
tapes:
high_vol: artifacts/simtrader/tapes/politics_high_vol_*/
low_vol: artifacts/simtrader/tapes/sports_low_vol_*/
new_market: artifacts/simtrader/tapes/new_market_first_4h_*/
```

```
# Command:
python -m polytool simtrader sweep \
--config market_maker_sweep.yaml \
--tape-glob "artifacts/simtrader/tapes/*/events.jsonl" \
--output artifacts/simtrader/sweeps/mm_v1/
```

## 4. Track A — Market Selection Engine

The market selection engine runs every 1–4 hours and determines which markets to deploy
capital into. This is critical — being in the right markets multiplies returns from the market
making strategy.

##### 4.1 Scoring Pipeline

# packages/polymarket/market_selection/scorer.py

```
import requests
from dataclasses import dataclass
```

```
@dataclass
class MarketScore:
market_slug : str
reward_apr_est : float # estimated daily reward / capital required
spread_score : float # current_spread / min_profitable_spread
```

fill_score : float # est. fills per hour from volume + spread
competition_score : float # 1 / (active_makers + 1) — fewer = better
age_hours : float # hours since market creation
composite : float # weighted sum

WEIGHTS = {
'reward_apr_est' : 0.35,
'spread_score' : 0.25,
'fill_score' : 0.20,
'competition_score': 0.15,
'age_factor' : 0.05, # bonus for new markets
}

def score_market(market: dict, orderbook: dict, reward_config: dict) ->
MarketScore:
mid = (market['best_bid'] + market['best_ask']) / 2
current_spread = market['best_ask'] - market['best_bid']

# Reward APR estimate

daily_reward = reward_config.get('reward_rate', 0.002) _
reward_config.get('min_size_cutoff', 50)
reward_apr = daily_reward / reward_config.get('min_size_cutoff', 50) _ 365

# Spread score: is the current spread wide enough to be profitable?

min_profitable_spread = 0.015 # 1.5¢ floor for 2% fee model to break even
spread_score = min(current_spread / min_profitable_spread, 3.0)

# Fill score: proxy from 24h volume

vol_24h = market.get('volume_24h', 0)
fill_score = min(vol_24h / 10000, 2.0) # normalize to $10K reference

# Competition: count active makers from orderbook depth analysis

makers_est = len([l for l in orderbook.get('bids', []) if l[1] < 50])
competition_score = 1.0 / (makers_est + 1)

# Age bonus: new markets get extra weight

age_hours = (market.get('age_seconds', 99999)) / 3600
age_factor = max(0, 1.0 - age_hours / 48.0) # decays to 0 after 48h

composite = (WEIGHTS['reward_apr_est'] _ min(reward_apr, 3.0) +
WEIGHTS['spread_score'] _ spread_score +
WEIGHTS['fill_score'] _ fill_score +
WEIGHTS['competition_score'] _ competition_score +
WEIGHTS['age_factor'] \* age_factor)

return MarketScore(
market_slug=market['slug'], reward_apr_est=reward_apr,
spread_score=spread_score, fill_score=fill_score,
competition_score=competition_score, age_hours=age_hours,
composite=composite
)

##### 4.2 Market Tiers & Capital Allocation

```
Tier Criteria Target
Spread
```

```
Capital
%
```

```
Expect
ed APR
```

```
Tier 1: New
Markets
```

```
< 48h old, spread 5–15¢, few
active makers
```

```
4–10¢ 30% 80–
%
```

```
Tier 2:
Reward
Markets
```

```
Active reward program, $50K+
daily volume, 2–4 makers
```

2–5¢ 40% 20–60%

```
Tier 3:
Volume
Markets
```

```
High volume, tight spread, many
makers
```

1–3¢ 20% 8–20%

```
Reserve Capital buffer for inventory
absorption and new opportunities
```

```
N/A 10% 0%
(buffer)
```

##### 4.3 Market Filters (Pre-Scoring)

Only markets passing all filters enter the scoring pipeline:

- **mid_price in [0.10, 0.90]:** Avoid near-resolution markets. Adverse selection risk spikes
  outside this range.
- **days_to_resolution > 3:** Minimum runway. Very short-dated markets have high inventory
  risk and thin rewards.
- **volume_24h > $5,000:** Minimum activity. Below this, fills are too rare to be worth the slot.
- **NOT recently resolved:** Exclude markets within 24h of expected resolution.
- **reward_config exists:** Only target markets with an active reward program (fetch from
  Gamma API).

```
# python -m polytool market-scan
python -m polytool market-scan \
--min-volume 5000 \
--top 20 \
--output artifacts/market_selection/current.json
```

```
# Output:
# artifacts/market_selection/current.json — ranked list with scores
# artifacts/market_selection/capital_plan.json — capital allocation per market
```

## 5. Track B — The Alpha Factory

The Alpha Factory is the system that transforms Polymarket public data into continuously
improving, validated trading strategies. It runs in parallel with Track A from day one. Every
component here either extends existing PolyTool infrastructure or adds a new layer on top of it.

```
Why Top Wallets Still Have Edge: The COMPLETE_SET_ARBISH detector already in
PolyTool flags wallets doing something more complex than simple binary arb. CLV analysis
shows these wallets consistently beat closing price — not by luck. The three most likely strategy
classes are: (1) combinatorial/correlation arb between related markets, (2) resolution timing arb
exploiting UMA oracle settlement windows, and (3) information advantage with faster news
feeds. All three are potentially capturable at retail latency. The Alpha Factory tells us which one
it is.
```

**COMPONENT 5.1 ·** _NEW · ~3 days_

#### wallet-scan — Top Wallet Discovery

```
Automatically surfaces the 50–200 most profitable Polymarket wallets by composite score.
Feeds directly into batch-run.
```

**Composite Scoring Formula**

```
composite_score = (
0.30 × log_normalized_realized_pnl # absolute profit (log scale, $1K ref)
+ 0.25 × win_rate # (WIN + PROFIT_EXIT) / all resolved
+ 0.25 × avg_clv_pct # CLV already computed by PolyTool scan
+ 0.10 × consistency_score # 1 / (1 + stdev_rolling_30d_pnl)
+ 0.10 × market_diversity_score # inverse HHI across categories
)
```

```
Pre-filters (applied before scoring):
min_trades >= 50 (statistical significance)
active_last_90_days = True
round_trip_filter = True (exclude wash trading: round-trip < 60s)
```

**Data Sources for Discovery**

**Source What It Returns Access Method Rate Limit**

```
Polymarket Data
API
```

```
User positions, trade
history, portfolio PnL
```

```
REST, already integrated
in PolyTool
```

~100 req/min

```
Gamma API Market metadata, volume,
category, rewards config
```

REST, public no-auth ~200 req/min

```
Polymarket
Subgraph
```

```
Wallet-level volume, trade
counts, token activity
directly on-chain
```

```
GraphQL via The Graph
(free tier)
```

500 req/day (free)

**Source What It Returns Access Method Rate Limit**

```
Dune Analytics
API
```

```
Pre-computed PnL
leaderboards from
community analysts
```

```
REST API (free tier: 100
queries/day)
```

100 queries/day

```
# New CLI
command
python -m
polytool
wallet-scan
\
--top 100
\
```

```
--min-trades
50 \
--output
top_wallets.
txt
```

```
# Feeds
directly
into
batch-run:
python -m
polytool
batch-run \
--users
top_wallets.
txt \
--workers
8 \
```

```
--compute-cl
v
--compute-pn
l
--enrich-res
olutions
```

**COMPONENT 5.2 ·** _NEW · ~5 days_

#### alpha-distill — LLM Strategy Extraction

```
Two-stage pipeline: mechanical pattern aggregation first (no LLM cost), then structured LLM
extraction into machine-readable StrategySpec JSON.
```

**Stage A: Mechanical Pre-Aggregation (No LLM)**

Before touching an LLM, aggregate patterns from hypothesis_leaderboard.json mechanically.
This eliminates noise and reduces LLM token cost by ~90%:

- **Cluster wallets** by strategy signature: timing patterns, entry price tiers, market types, CLV
  distribution
- **Identify recurring segments** appearing in 5+ wallets with positive CLV (cross-wallet signal
  = real edge)
- **Compute per-segment stats:** avg position size, hold duration, win rate, CLV, category
  concentration
- **Output:** pattern_candidates.json — pre-aggregated evidence ready for LLM

**Stage B: StrategySpec JSON Output Schema**

```
// StrategySpec schema — output by alpha-distill
{
"strategy_id": "news-timing-politics-v1", // kebab-case
"strategy_class": "market_making | directional | arb | timing | copy",
"hypothesis": "one sentence: what edge does this strategy exploit?",
"entry_rules": {
"market_filter": "category=Politics, mid in [0.30, 0.70], age > 2d",
"trigger": "what event or condition triggers entry",
"entry_price_range": [0.30, 0.70],
"position_size_rule": "kelly | fixed_usdc | vol_scaled"
},
"exit_rules": {
"take_profit": "price target or % gain",
"stop_loss": "price target or % loss",
"time_exit": "max hold duration in hours"
},
"execution_requirements": {
"max_acceptable_latency_ms": 500,
"requires_live_feed": true,
"requires_news_feed": false,
"min_capital_usdc": 500
},
"falsification": "what SimTrader result proves no edge?",
"confidence": "high | medium | low",
"supporting_wallets": ["slug1", "slug2"],
"key_evidence": "avg CLV +4.2% across 23 positions in 8 wallets"
}
```

```
# Run alpha-distill after batch-run completes
python -m polytool alpha-distill \
--batch-root artifacts/research/batch_runs/2026-03-04/<batch_id>/ \
--min-wallets 5 \
--min-clv 0.02 \
--output strategy_candidates/
```

**COMPONENT 5.3 ·** _NEW · ~1 week_

#### strategy-codify — Spec to Runnable Code

```
Converts a StrategySpec JSON into a runnable SimTrader strategy class. Full automation for
market-making and copy strategies. Skeleton code for complex arb strategies.
```

**Strategy Class Automation
Level**

**Generated Output**

market_making Full — no dev
work

```
YAML config pointing at MarketMakerStrategy. Runs
immediately.
```

copy (follow
wallet)

```
Full — no dev
work
```

Config for copy_wallet_replay pointing at source wallets.

timing (enter
before event)

```
High — review
trigger
```

```
Strategy class with configurable entry window, price range,
category filter.
```

arb
(combinatorial)

```
Medium —
dev fills pair
logic
```

```
Class with market_pair_filter, correlation_threshold,
spread_threshold hooks.
```

arb (resolution
timing)

```
High — review
oracle logic
```

```
Class with settlement_window_hours, oracle_type,
position_direction.
```

directional
(news-driven)

```
Medium —
dev fills signal
hook
```

```
Skeleton class with signal_context injection point and TODO
markers.
```

```
# Generate
runnable
strategy
from spec
python -m
polytool
strategy-cod
ify \
--spec
strategy_can
didates/stra
tegy_specs.j
son \
--output
packages/pol
ymarket/simt
rader/strate
gies/generat
ed/ \
--dry-run
# preview
before
writing
```

**COMPONENT 5.4 ·** _EXTEND SimTrader · ~4 days_

#### Validation Gate — 3-Level Protocol

```
Every generated strategy must pass multi-tape replay, scenario sweep (with latency injection),
and shadow live validation before touching real capital.
```

**Level 1: Multi-Tape Replay (Gate: 70% positive)**

- **Run strategy on 20+ diverse tapes** spanning ≥ 3 distinct time periods and market types
- **Include stress tapes:** high-volatility, major news events, new market launches,
  low-liquidity
- **Gate criterion:** positive net PnL (after 2% fee model) on ≥ 70% of tapes. Compute Sharpe,
  max drawdown, avg hold.

**Level 2: Scenario Sweep (Gate: profitable at realistic_retail)**

```
# Scenario sweep config for arb strategies
scenarios:
base_case: {latency_ms: 0, fill_rate: 1.00, slippage_bps: 0}
realistic_retail: {latency_ms: 150, fill_rate: 0.70, slippage_bps: 5}
degraded: {latency_ms: 500, fill_rate: 0.40, slippage_bps: 15,
dropped_updates_pct: 5}
worst_case: {latency_ms: 1000, fill_rate: 0.20, slippage_bps: 30,
dropped_updates_pct: 10}
```

```
Gate:
PASS if profitable at realistic_retail
CONDITIONAL if only profitable at base_case → requires co-location
infrastructure
FAIL if only profitable at worst_case inversion
```

**Level 3: Shadow Validation (Gate: shadow PnL within 25% of replay)**

- **30-day shadow run** on live market data with no real orders
- **Compare shadow fills** to what replay predicted — measures model accuracy
- **Gate:** shadow PnL within 25% of replay prediction. Higher deviation = model needs
  revision.

**COMPONENT 5.5 ·** _EXTEND existing RAG · ~4 days_

#### Triple RAG Architecture

```
Three completely separate knowledge bases with strict write policies. Nothing crosses tiers
without a gate.
```

**RAG Layer Contents Trust Level Write Policy Query Use
Case**

User RAG
(existing)

```
All dossiers, scan
artifacts, hypotheses,
LLM reports, audit
outputs
```

```
Exploratory
(low/med)
```

```
Automated pipeline +
LLM reports
```

```
Research: What
patterns did
wallet X show
last month?
```

Research
RAG (new)

```
Only validated strategy
specs, proven patterns,
books/papers, live
performance records
```

```
High
(curated
only)
```

```
Validation gate PASS
+ human explicit
approval
```

```
Execution: What
strategy fits
current market
conditions?
```

Signals RAG
(new)

```
Proven news/social
signal-reaction
patterns. Events that
moved markets ≥3%
repeatedly.
```

```
Medium
(time-sensiti
ve)
```

```
Auto: if pattern
significance threshold
met after ≥10 events
```

```
Real-time: Does
this news match
a pattern that
historically
moved this
market?
```

```
Critical
Write
Policy:
NOTHING
enters the
Research
RAG without
passing the
Validation
Gate. This is
the hardest
discipline to
maintain —
and the
most
valuable.
After 6
months, the
Research
RAG is a
competitor
moat: 20–50
validated
specs with
live
performance
records, a
graveyard of
failed
strategies
with
post-mortem
s, and signal
patterns
```

```
RAG Layer Contents Trust Level Write Policy Query Use
Case
```

```
proven
against real
market
reactions.
```

```
kb/research/ ← NEW: high-trust only
strategies/
validated/
<strategy_id>/
strategy_spec.json ← from alpha-distiller
validation_report.json ← from validation gate (3 levels)
live_performance_30d.json ← from bot feedback loop
archived/ ← strategies that failed live
patterns/
recurring_cross_wallet/
sources/ ← books, papers (via cache-source)
```

```
kb/users/ ← EXISTING: unchanged
kb/signals/ ← NEW: live signals + measured reactions
markets/<market_slug>/
signals/ ← linked news/social items
reactions/ ← price change measurements
```

**COMPONENT 5.6 ·** _NEW · ~1.5 weeks_

#### News / Social Ingest + Market Linker

```
Ingest external signals, link to specific markets, MEASURE how markets actually reacted, store
only proven patterns. Integrates with your senior dev's existing project.
```

**Signal Sources & Ingestion**

```
Source Signal Type Python Library Collection
Frequency
```

```
RSS (AP,
Reuters, BBC,
ESPN,
Bloomberg)
```

```
Article headlines,
summaries,
publication time,
entities
```

feedparser Every 5 minutes

```
Twitter/X (filtered
accounts list)
```

```
Political accounts,
sports journalists,
crypto news,
Polymarket official
```

```
Nitter scraper or Twitter
API v2
```

Every 2 minutes

```
Reddit (r/politics,
r/sportsbook,
r/CryptoMarkets)
```

```
Hot post titles,
upvote velocity,
comment counts
```

```
PRAW (Python Reddit
API Wrapper)
```

Every 15 minutes

```
Source Signal Type Python Library Collection
Frequency
```

```
Telegram (public
channels)
```

```
Crypto news
channels,
Polymarket
community
announcements
```

telethon or pyrogram Real-time

```
Polymarket
Discord
```

```
Official
announcements,
new market
launches,
resolution notices
```

discord.py bot Real-time

**Reaction Measurement (The Critical Addition)**

This is what transforms a news feed into a trading signal. For every signal linked to a market,
measure the actual price reaction:

```
-- ClickHouse table: market_signal_reactions
CREATE TABLE market_signal_reactions (
signal_id String,
market_slug String,
signal_ts DateTime64(3, 'UTC'),
link_confidence Float32, -- 0.0–1.0: how certain is this signal linked
to this market?
price_at_signal Float32,
price_5min_after Float32,
price_30min_after Float32,
price_2hr_after Float32,
price_change_5min Float32, -- price_5min_after - price_at_signal
price_change_30min Float32,
max_move_30min Float32, -- max abs move in 30-min window
signal_source String, -- rss | twitter | reddit | telegram | discord
signal_text String,
signal_sentiment String, -- positive | negative | neutral
(LLM-classified)
market_moved_pct Float32, -- abs(price_change_30min) / price_at_signal
pattern_validated Bool -- true only when archived to Signals RAG
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(signal_ts)
ORDER BY (signal_ts, market_slug)
```

**Market Linker Logic**

1. **Entity extraction:** pull named entities from signal text (people, orgs, events, locations)
2. **Category matching:** map entities to Polymarket categories (Politics, Sports, Crypto,
   Economics)
3. **Market search:** query Gamma API for active markets matching entities + category

4. **LLM disambiguation:** for ambiguous cases, ask a local LLM "does this news affect this
   market? confidence 0–1"
5. **Write to ClickHouse:** signal + market link + confidence → market_signal_reactions table
6. **Measure reaction:** scheduled job at t+5min, t+30min, t+2hr writes price change back to
   row
7. **Validate pattern:** if same signal type + category shows market_moved_pct > 3% in 10+
   historical events → validated → Signals RAG

**Integration with Senior Dev's Project**

```
Dev's Existing
Component
```

**Maps To Integration Work Needed**

```
News/RSS/Twitter ingest
pipeline
```

```
Component 5.6
Signal Ingestion
```

```
Low — wrap output into market_signals
ClickHouse schema
```

```
ChromaDB or vector store
for news
```

```
Signals RAG (third
layer)
```

```
Low — keep separate from User RAG +
Research RAG. Add write policy gating.
```

```
Market linking logic (news
→ markets)
```

```
Component 5.6
Market Linker
```

```
Medium — extend with Gamma API call for
specific token IDs and CLOB tradeable assets
```

```
LLM classification of news
relevance
```

Link confidence score Low — wire output into link_confidence field

```
Historical pattern storage Pattern Archive →
kb/signals/
```

```
Medium — add reaction measurement (the new
part: price_change_5min etc.)
```

**COMPONENT 5.7 ·** _NEW · ~3 days_

#### Closed-Loop Feedback

```
Bot performance writes back into the Research RAG. Strategies that beat predictions get
promoted. Underperformers get archived with post-mortems. System gets smarter continuously.
```

```
# Weekly feedback evaluation per strategy_id
for strategy in active_strategies:
perf_ratio = live_pnl_7d / predicted_pnl_from_validation_report
```

```
if perf_ratio >= 0.75:
action = "KEEP"
# Write 7-day performance report to Research RAG
```

```
elif perf_ratio >= 0.40:
action = "REVIEW"
# Reduce capital allocation by 50%
# Flag for human review: has market microstructure changed?
# Re-check if source wallets have adapted strategy
```

else: # perf_ratio < 0.40

```
action = "AUTO_DISABLE"
# Move to Research RAG as archived with post-mortem
# Trigger: re-run alpha-distill on source wallets
# (they may have changed strategy)
```

## 6. Advanced Strategies — Arb, Information

## Advantage & Scale

These strategies activate after the base market maker is live and the Alpha Factory has
produced its first validated StrategySpecs. Each one requires the execution infrastructure from
Track A and benefits from the research data from Track B.

```
Correcting the Prior Roadmap: Simple binary arb (YES + NO combined best_ask < $1) is
dead at retail latency — 73% of windows are sub-100ms. This document treats that as closed.
BUT: combinatorial arb, resolution timing arb, and information advantage are a completely
different class. The Alpha Factory will tell you which one the top wallets are running. This
section provides the full construction spec for each.
```

##### 6.1 Arb Strategy Testing Protocol

Every arb strategy discovered by alpha-distill must answer two questions before
implementation:

**Question Test Method Gate Criterion**

```
Did the edge EXIST
historically?
```

```
Level 1: Multi-tape replay (20+ tapes) Positive net PnL on ≥ 70% of
tapes
```

```
Can we CAPTURE it at
our latency?
```

```
Level 2: Scenario sweep with latency
injection
```

```
Profitable at realistic_retail
(150ms latency, 70% fill rate)
```

```
Is it durable, not
one-off?
```

```
Level 3: 30-day shadow run on live
markets
```

```
Shadow PnL within 25% of
replay prediction over 30 days
```

##### 6.2 Combinatorial / Correlation Arb

Some Polymarket markets are logically linked. When the implied joint probability diverges from
what the correlated market prices imply, there is a capturable opportunity that does NOT require
sub-100ms execution.

- **Example:** Trump wins 2028 (65%) and Republicans win Senate 2028 (45%). Historical
  correlation ~0.82. The implied joint P(Trump wins AND Senate Republican) should be
  ~0.53, but Polymarket implies 0.65 × 0.45 = 0.29. Gap exists.
- **Latency requirement:** Correlation divergences typically persist for minutes, not
  milliseconds. Retail-executable.

```
# packages/polymarket/simtrader/strategies/combinatorial_arb.py
# Core logic sketch
```

```
class CombinatorialArbStrategy:
"""
Monitors pairs of correlated markets.
Enters when implied joint probability diverges from historical correlation.
```

```
Entry trigger:
implied_correlation = YES_A_price × YES_B_price / max(YES_A_price,
YES_B_price)
historical_correlation = from ClickHouse rolling 30-day data
```

```
if abs(implied - historical) > divergence_threshold:
→ buy underpriced market, sell (via NO) overpriced market
```

```
Exit:
→ when correlation re-converges to within exit_threshold
→ OR time_exit (max hold 24h)
```

```
Risk:
→ correlation can structurally break on major news (hedge with stop_loss)
→ pairs must share resolution timeframe (no arb if different resolution
dates)
"""
```

```
def compute_correlation(self, market_a_slug, market_b_slug,
lookback_days=30) -> float:
# Query ClickHouse: daily closing prices for both markets
# Compute Pearson correlation of price series
...
```

```
def find_divergences(self, market_pairs: list[tuple]) -> list[dict]:
# For each pair, compute implied vs historical correlation gap
...
```

```
Where PolyTool Already Helps: The COMPLETE_SET_ARBISH detector already flags wallets
potentially doing this. The segment_analysis category breakdown shows which categories the
target wallet concentrates in. If two high-CLV wallets both concentrate in Politics + Economics
with strong co-entry timing, that is the combinatorial arb signal.
```

##### 6.3 Resolution Timing Arb

Polymarket uses the UMA Optimistic Oracle (OO) for dispute resolution. The settlement process
has a defined timeline that most traders do not track precisely. This creates exploitable
windows.

**UMA Optimistic Oracle Settlement Timeline**

```
Market resolves → UMA proposes outcome → 2-hour LIVENESS_PERIOD begins
During liveness: price is "proposed" but not settled
After liveness: price is SETTLED → CTF pays out
```

```
The arbitrage window:
When UMA proposes payout = YES (1.0) but market is still trading at 0.85-0.92
→ buy YES immediately for risk-free 8-15¢ profit
→ hold for 2 hours until settlement pays 1.0
```

```
Why it works:
Most traders watch Gamma API for resolution. Gamma sometimes lags UMA by
minutes.
PolyTool already has OnChainCTFProvider reading direct Polygon RPC state.
We can see UMA proposal before Gamma reflects it.
```

```
# Resolution timing arb implementation sketch
class ResolutionTimingArb:
"""
Monitors UMA Optimistic Oracle for proposal events.
When a proposal appears that contradicts current market price:
→ take position in direction of proposal
→ hold until settlement (T + 2h liveness)
```

```
Data source: OnChainCTFProvider (already in PolyTool R3)
Event to watch: UMA OptimisticOracle ProposePrice event
Implementation: subscribe to Polygon WS for contract events
"""
```

```
async def watch_proposals(self, market_addresses: list[str]):
# Subscribe to Polygon WS: eth_subscribe('logs', {address: uma_oracle})
# Filter for ProposePrice(bytes32 identifier, uint256 timestamp,
# int256 proposedPrice, ...)
# When proposedPrice = 1e18 (YES) and market price < 0.90:
# → place BUY order immediately
...
```

```
Latency Requirement: Resolution timing arb has a 2-HOUR window (UMA liveness period).
This is NOT a latency-sensitive strategy. A 500ms execution delay is irrelevant. This is the most
accessible arb class in this entire document because it does not require co-location or
sub-100ms infrastructure.
```

##### 6.4 Information Advantage Strategies

Markets lag behind information by 30 seconds to 5 minutes. When a news event has a clear,
high-confidence directional impact on a specific market, and the market has not yet moved,
there is a directional trading opportunity.

**Classifier Architecture**

```
# News → Market Impact Classifier
# Input: news item text + target market question
# Output: (affected: bool, direction: 'YES'|'NO'|'NEUTRAL', confidence: 0-1)
```

```
prompt_template = """
Market question: {market_question}
News item: {news_text}
Published: {published_at}
```

```
Does this news item meaningfully affect the probability of YES resolution
for this market? If yes, does it increase (YES) or decrease (NO) the
probability? How confident are you (0.0 = no idea, 1.0 = certain)?
```

```
Respond in JSON: {"affected": bool, "direction": "YES|NO|NEUTRAL", "confidence":
float}
"""
```

```
# Use fast local LLM (Llama-3-8B via Ollama) for low latency
# Threshold: confidence > 0.75 AND current market_moved_pct < 1% → entry signal
```

**Execution Rules for Information Arb**

- **Position size:** 5% of capital max per trade (higher conviction but higher risk than MM)
- **Auto-exit:** exit if market moves against by 3% within 10 minutes (news was wrong or
  already priced in)
- **Don't chase:** if market has already moved 4%+ before our order, skip (opportunity passed)
- **Category restriction:** only trade categories where the signal-reaction database shows
  consistent moves (from Signals RAG)

##### 6.5 15-Minute Crypto Markets (Quick Win)

Polymarket posts BTC/ETH/SOL up/down markets resolved by Chainlink price at specific
15-minute timestamps. These have a structural edge available now.

```
# 15-min crypto strategy: Flash crash mean reversion
# Reference: discountry/polymarket-trading-bot GitHub repo
```

Strategy:

1. Monitor BTC/ETH price via Pyth or Chainlink price feed WebSocket
2. If intra-bar price drops > threshold% in < 5 minutes:
   → historical mean reversion probability > 70% in 15-min window
   → buy NO (price did NOT continue down to end of bar)
3. Exit at resolution or at +5% profit

```
Data sources:
Pyth Network: wss://hermes.pyth.network/ws (free, sub-second latency)
Chainlink MATIC mainnet: 0xAB594600376Ec9fD91F8e885dADF0CE036862dE0 (BTC/USD)
```

```
Advantage:
Chainlink price is DETERMINISTIC — we know exactly what will resolve the market.
No LLM needed. Pure statistical mean-reversion edge.
Implementation time: ~3 days once execution layer is live.
```

## 7. Live Deployment — Infrastructure &

## Operations

Deployment follows a staged capital approach. Infrastructure is minimal at Stage 1. Scale with
confidence, not with hope.

##### 7.1 Infrastructure Requirements

```
Component Provider Cost/Mo
nth
```

**Why This Choice**

```
VPS (trading
server)
```

```
QuantVPS or Vultr
(NY/NJ datacenter)
```

```
$30–100 4–12ms to Polymarket CLOB. Low latency
matters for market making cancel-replace
cycles.
```

```
Polygon RPC Chainstack or
Alchemy dedicated
node
```

```
$50–100 Public nodes throttle at peak hours and drop
WebSocket connections. Unacceptable for
live trading.
```

```
Monitoring Existing Grafana +
new panels
```

```
$0
(already
running)
```

```
Add: P&L panel, open orders, fill rate,
inventory skew, signal reaction latency.
```

```
Alerts python-telegram-bot $0 Real-time Telegram alerts on: new fill,
position limit breach, daily loss cap, WS stall,
kill switch.
```

```
Secrets VPS environment
variables (systemd
environment files)
```

```
$0 Never in code. Never in git. PK,
CLOB_API_KEY, CLOB_API_SECRET,
CLOB_API_PASSPHRASE.
```

##### 7.2 Staged Capital Deployment

**Stage Capital Duration Success Criterion Action on Pass**

```
Stage 0:
Paper Live
```

```
$0 (dry-run) 72 hours Zero errors, P&L estimate positive,
kill switch + reconnect tested
```

```
Proceed to
Stage 1
```

```
Stage 1:
Micro
```

```
$500 USDC 7 days Positive realized PnL + rewards
after 7 days. No risk manager
violations.
```

Scale to Stage 2

```
Stage 2:
Small
```

```
$5,000
USDC
```

```
2 weeks Consistent daily positive PnL. All
risk controls proven under real fills.
```

Scale to Stage 3

```
Stage 3:
Scale-1
```

```
$25,000
USDC
```

```
Ongoing $75–250/day target. 10+ markets.
First Alpha Factory strategy
deployed on top.
```

Continue scaling

```
Stage 4:
Scale-2
```

```
$100,000
USDC
```

```
Ongoing $300–800/day. Multi-bot
architecture. Proven 3+ validated
strategies running.
```

```
Professional LP
territory
```

```
Important Caveat: The P&L figures above ($75–250/day at $25K) are based on
community-reported results from Polymarket market makers in 2025–2026 and the reward
program rates at time of writing. These are not guarantees. Actual results depend on market
selection quality, spread calibration, inventory management, and reward program continuation.
Always validate at Stage 1 before scaling.
```

##### 7.3 Daily Operations Runbook

# DAILY SCHEDULE

```
07:00 UTC — Market scan
python -m polytool market-scan --min-volume 5000 --top 20
```

```
07:05 UTC — Bot reload with new market selection
python -m polytool simtrader live --reload-markets
```

```
Continuous — Bot event loop
receive book_update → compute A-S reservation price + spread
→ if reprice threshold exceeded: cancel existing → place new bid + ask
→ risk check passes → executor sends to CLOB
→ fills written to artifacts/simtrader/live_runs/
```

00:00 UTC — Polymarket rewards credited automatically to wallet

DAILY REVIEW (5 min)

- Open Grafana: fill rate, P&L attribution, inventory drift
- Check Telegram alerts for any triggered risk limits
- Review market_selection ranking: any new Tier 1 markets to add?

WEEKLY REVIEW (30 min)

- Run alpha-distill on latest batch-run output

- Check Signals RAG for any newly validated news patterns
- Review feedback loop: any strategies underperforming by >40%?

##### 7.4 WebSocket Reconnection & Resilience

```
# WS event loop with reconnect + kill switch
async def run_event_loop(runner: LiveRunner, market_id: str):
backoff = 1.0
while True:
try:
check_or_raise() # kill switch check
```

```
async with websockets.connect(WS_URL) as ws:
backoff = 1.0 # reset on successful connection
await
ws.send(json.dumps({"type":"subscribe","channel":"market","assets_ids":[market_id]
}))
```

```
async for message in ws:
check_or_raise() # check on every event
event = json.loads(message)
orders = runner.on_event(event)
```

```
for order in orders:
if order['action'] == 'limit':
await runner._place_order(Order(**order))
elif order['action'] == 'cancel':
await runner._cancel_order(order['id'])
elif order['action'] == 'cancel_all':
await runner.emergency_stop()
```

```
except websockets.exceptions.ConnectionClosed:
print(f"[WS] Disconnected. Cancelling all orders. Retry in
{backoff}s")
await runner.emergency_stop() # cancel all on disconnect
await asyncio.sleep(backoff)
backoff = min(backoff * 2, 60.0) # exponential backoff, cap 60s
```

```
except RuntimeError as e:
if "KILL SWITCH" in str(e):
print(f"[HALT] {e}")
await runner.emergency_stop()
return
raise
```

## 8. Risk Management Framework

Risk management is not optional plumbing — it is the difference between a learning system and
a catastrophic loss. Every parameter below is a starting value to be tightened as the bot proves
itself.

##### 8.1 Pre-Trade Checks (RiskManager)

**Check Default Value What It Prevents**

```
Max position per market $500 USDC Single market concentrates too much capital →
adverse selection destroys one bad position
```

```
Max total notional 80% of USDC
balance
```

```
Bot locks up all capital in open orders → no liquidity
buffer
```

Max single order size $200 USDC A mis-typed config enters a $10K order

```
Daily loss cap $100 USDC
(Stage 1)
```

```
Strategy is broken for today's market conditions →
let it blow through $100, not $5,000
```

```
Inventory skew limit $400 USDC
abs(long-short)
```

```
Market is moving against inventory → stop making it
worse
```

##### 8.2 Kill Switch Hierarchy

8. **File kill switch:** touch artifacts/simtrader/KILL — checked before every order placement
9. **Daily loss cap:** RiskManager.check_order returns False when daily_pnl < −cap → all new
   orders blocked
10. **WS disconnect:** event loop detects ConnectionClosed → emergency_stop() cancels
    all → exponential backoff
11. **Inventory limit:** MarketMakerStrategy returns cancel_all action when abs(inventory_usdc)
    > max_inventory
12. **Manual Telegram command:** operator sends /stop → triggers arm_kill_switch()
    remotely

##### 8.3 Wallet Security

**Layer Implementation**

Primary capital Cold storage hardware wallet. Never on VPS. Never in .env.

```
Trading hot wallet Separate wallet. Funded with only the current stage capital. If compromised,
loss is bounded.
```

**Layer Implementation**

```
API key derivation Private key → CLOB API credentials via py-clob-client. Trading key ≠ funded
address.
```

```
Proxy wallet pattern Use Polymarket's EIP-712 proxy wallet: signing key separate from funded
address.
```

```
USDC allowance One-time USDC approval to Polymarket CTF exchange contract. Limit to 2×
current stage capital.
```

##### 8.4 Regulatory Note

```
Jurisdiction Check Required: Polymarket restricts access to users from certain jurisdictions
including the United States. Before deploying any live capital, verify you are operating from an
eligible jurisdiction per Polymarket's Terms of Service. This document does not constitute legal
advice. All trading activity is the sole responsibility of the operator.
```

## 9. Complete Phase Timeline — Week by

## Week

### 2

```
Weeks to First Live
Orders
```

### 5–6

```
Weeks to First
Discovered Strategy
```

### 8

```
Weeks to Alpha Factory
Running
```

### 12+

```
Full System
(Multi-Strategy)
```

```
We
ek
```

**Track A (Execution) Track B (Alpha Factory) Gate Criterion**

```
1 Build executor.py +
wallet.py + risk.py +
kill_switch.py. Unit tests
for each.
```

```
wallet-scan command: score
top 100 wallets. Output
top_wallets.txt.
```

```
executor.place_limit_order() works
in dry-run mode
```

```
2 Build live_runner.py.
Extend SimTrader CLI
with --live flag.
MarketMakerStrategy v1
in replay.
```

```
batch-run on 20 wallets
(CLV + PnL + resolutions).
First
hypothesis_leaderboard.jso
n.
```

```
dry-run end-to-end: market_maker
places and cancels orders without
error
```

```
We
ek
```

**Track A (Execution) Track B (Alpha Factory) Gate Criterion**

```
3 Market selection engine
(market-scan). A-S
parameter sweep on 15+
tapes. Gate: 70%
positive.
```

```
alpha-distill v0 (manual LLM
step):
pattern_candidates.json →
first StrategySpec.
```

```
Sweep: ≥ 10/15 tapes positive PnL
after 2% fees
```

```
4 30-day shadow run starts.
Infrastructure setup: VPS
+ Polygon RPC +
Grafana panels.
```

```
Strategy-codify: first
generated strategy class.
Level 1 validation on first
StrategySpec.
```

```
Shadow run stable 72h: no errors,
kill switch tested, reconnect tested
```

```
5 STAGE 0 → STAGE 1:
$500 live deployment.
Market maker running on
3–5 markets.
```

```
News ingest pipeline
connected to ClickHouse.
market_signals table
populating.
```

```
First real fill confirmed. Daily PnL
positive after Week 1.
```

```
6 Review Stage 1 PnL.
Scale to $5K (Stage 2) if
criterion met.
```

```
First discovered strategy
passes Level 2 (scenario
sweep). Deploy it on live
bot.
```

```
Stage 2 deployed. First non-MM
strategy live.
```

```
7–
8
```

```
$5K stable. Add 5 more
markets. Tune A-S
parameters from real fill
data.
```

```
batch-run automated daily
on 100 wallets. Research
RAG v1 with first validated
spec.
```

```
Consistent daily positive PnL
across all active markets
```

```
9–
12
```

```
Scale to $25K (Stage 3).
10+ markets.
Multi-strategy concurrent
operation.
```

```
Signals RAG: first validated
news patterns. Information
arb classifier deployed.
```

```
$75–250/day target PnL. 3+
strategies simultaneously active.
```

```
Mo
nth
3+
```

```
$100K+ scale. Multi-bot
architecture. Kelly sizing.
```

```
Alpha Factory fully
automated. New strategies
deployed weekly.
```

```
$300–800/day. System improving
without manual intervention.
```

## 10. Scale Architecture — Month 3+

Once the base system is profitable and the Alpha Factory has produced 3+ validated strategies,
the architecture evolves to multi-bot with centralized capital management.

##### 10.1 Multi-Bot Architecture

Central Capital Manager

```
├── Market Maker Bot (70% capital)
│ ├── 20–50 markets simultaneously
│ ├── A-S model with real-time parameter adaptation
│ └── Tier 1/2/3 market rotation every 4h
│
├── Alpha Bot (20% capital)
│ ├── Discovered strategies from Research RAG
│ ├── Information arb (news signal → directional trade)
│ ├── 15-min crypto markets (Chainlink oracle edge)
│ └── Correlation arb (combinatorial pair trades)
│
├── Resolution Arb Bot (10% capital)
│ ├── Monitors UMA Optimistic Oracle proposals
│ ├── Acts when proposed price ≠ current market price
│ └── 2-hour hold to settlement (no latency requirement)
│
└── Capital Manager (supervises all bots)
├── Daily rebalances capital allocation
├── Enforces portfolio-level risk limits
├── Triggers alpha-distill → strategy-codify when new patterns found
└── Archives underperforming strategies automatically
```

##### 10.2 Kelly Criterion Position Sizing

```
Reference: Kelly, J.L. (1956). "A New Interpretation of Information Rate." Bell System Technical
Journal, 35(4), 917–926. Kelly Criterion maximizes expected logarithmic growth of capital. For
binary markets with known edge, it gives the theoretically optimal bet size.
```

```
# Kelly Criterion for binary prediction markets
# For a strategy with win_rate p and average payout odds b:
```

kelly_fraction = (b·p - (1-p)) / b

```
Where:
p = historical win rate for this strategy on this market category
b = average payout when correct (1/entry_price - 1)
```

```
Example: strategy wins 65% of the time, entry at 0.55
b = (1/0.55) - 1 = 0.818
kelly = (0.818 × 0.65 - 0.35) / 0.818 = 0.222 → bet 22.2% of capital
```

```
Full Kelly is aggressive. Use half-Kelly in practice:
half_kelly = kelly_fraction / 2 = 0.111 → bet 11.1% of capital
```

```
Implementation in AlphaBot:
For each strategy + market_category combination:
estimate p from StrategySpec validation report
estimate b from current market mid price
size = half_kelly × available_capital_for_this_strategy
clamp to [min_size, max_position_per_market]
```

##### 10.3 Adverse Selection Detection

As the market maker scales, it will increasingly face informed traders (people with better
information than us). Detect and defend:

```
# Adverse selection detection signals
adverse_selection_indicators = [
# 1. Order flow imbalance (OFI)
# If 80%+ of fills in last 5 minutes are on one side → informed flow
ofi = (buy_volume - sell_volume) / (buy_volume + sell_volume)
if abs(ofi) > 0.7: widen_spread(multiplier=2.0)
```

```
# 2. Large orders eating deep into book
# If single order > 5× our quote size hits us → widen
if fill_size > 5 * our_order_size: widen_spread(multiplier=1.5,
duration_seconds=120)
```

```
# 3. Rapid mid-price movement after our fill
# If mid moves 3%+ within 30 seconds of our fill → we were adversely selected
# Track this in ClickHouse and update A-S γ parameter accordingly
```

```
# 4. High OFI + news signal correlation
# Cross-reference OFI spike against market_signal_reactions table
# If OFI spike coincides with news event → expected; don't widen
# If OFI spike with no news → unexplained informed flow → widen + flag
```

## References

All external sources cited in this document. Internal PolyTool documents are referenced by their
docs/ path.

##### Academic Papers

13. **[1] Avellaneda, M. & Stoikov, S. (2008).** 'High-frequency trading in a limit order book.'
    Quantitative Finance, 8(3), 217–224. Primary reference for reservation price and optimal
    spread formulas in Section 3.
14. **[2] Guéant, O., Lehalle, C-A., & Fernandez-Tapia, J. (2013).** 'Dealing with the
    inventory risk: a solution to the market making problem.' Mathematics and Financial
    Economics, 7(4), 477–507. Extends A-S to closed-form solutions with inventory boundary
    conditions.
15. **[3] Kelly, J.L. (1956).** 'A New Interpretation of Information Rate.' Bell System Technical
    Journal, 35(4), 917–926. Foundation for Kelly Criterion position sizing in Section 10.2.

16. **[4] Ho, T. & Stoll, H.R. (1981).** 'Optimal dealer pricing under transactions and return
    uncertainty.' Journal of Financial Economics, 9, 47–73. Original dealer pricing model that
    A-S extends.
17. **[5] Cartea, A., Jaimungal, S., & Penalva, J. (2015).** Algorithmic and High-Frequency
    Trading. Cambridge University Press. Comprehensive treatment of market making theory
    including inventory constraints and directional bets.

##### Open Source References

18. **[6] Polymarket/py-clob-client.** GitHub. Official Python SDK for Polymarket CLOB
    API. EIP-712 signing, order placement, position management.
    https://github.com/Polymarket/py-clob-client
19. **[7] Polymarket/agents.** GitHub. Official news + market intelligence framework. RSS
    ingest, ChromaDB, Gamma API integration. Reference for Component 5.6.
    https://github.com/Polymarket/agents
20. **[8] discountry/polymarket-trading-bot.** GitHub. 15-minute crypto market strategy
    reference. Flash crash detection, Chainlink price feed integration, Gamma API polling
    patterns. Reference for Section 6.5.
21. **[9] lorine93s/polymarket-market-maker-bot.** GitHub. Community market maker
    reference. Cancel/replace cycle logic, inventory management, quote skewing patterns.
22. **[10] Hummingbot. (2021).** 'A Comprehensive Guide to Avellaneda & Stoikov's
    Market-Making Strategy.' Hummingbot Blog. Practical implementation of A-S in a
    production trading system.

##### PolyTool Internal Documents

23. **[P1] SPEC-0004-fee-estimation-heuristic.md.** Fee model: 2% on gross profit. Used
    throughout as the cost model for profitability analysis.
24. **[P2] SPEC-0009-clv-and-price-context.md.** Closing Line Value definition and
    computation. CLV = closing_price − entry_price for binary markets.
25. **[P3] SPEC-0010-simtrader-vision-and-roadmap.md.** SimTrader architecture,
    BrokerSim fill model, L2 queue position logic, fault injection specification.
26. **[P4] STRATEGY_PLAYBOOK.md.** Resolution outcome taxonomy
    (WIN/LOSS/PROFIT_EXIT/LOSS_EXIT), EV framework, falsification methodology.
27. **[P5] FEATURE-batch-run-hypothesis-leaderboard.md.** batch-run command spec.
    Notional-weighted CLV aggregation. Deterministic leaderboard schema.
28. **[P6] PLAN_OF_RECORD.md.** Mission, constraints, artifact contract, canonical
    workflow. Foundation document for entire system.

##### Market Data References

29. **[M1] Polymarket CLOB API Documentation.** clob.polymarket.com — Rate limits (60
    orders/min), order types, WebSocket subscription schema.

30. **[M2] Polymarket Gamma API Documentation.** gamma-api.polymarket.com —
    Market discovery, rewards configuration, resolution data.
31. **[M3] Polymarket Liquidity Rewards Program.** Reward distribution data: $12.86M
    distributed to 66,000 addresses in February 2026. New market APR range 80–200%.
    Two-sided multiplier ~3×. Source: Polymarket official reward program documentation.
32. **[M4] UMA Optimistic Oracle Documentation.** docs.uma.xyz — Liveness period (2
    hours), ProposePrice event structure, dispute resolution timeline. Reference for Section
    6.3.
33. **[M5] Pyth Network Documentation.** pyth.network — Real-time price feeds for
    BTC/ETH/SOL via WebSocket (hermes.pyth.network/ws). Reference for Section 6.5.
34. **[M6] Chainlink Price Feeds (Polygon).** BTC/USD contract:
    0xAB594600376Ec9fD91F8e885dADF0CE036862dE0 on Polygon mainnet. Reference for
    15-min crypto market strategy.

_— End of PolyTool Construction Manual —_
