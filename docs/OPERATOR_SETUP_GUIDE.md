# Operator Setup Guide

See also: [OPERATOR_QUICKSTART.md](OPERATOR_QUICKSTART.md), [LIVE_DEPLOYMENT_STAGE1.md](runbooks/LIVE_DEPLOYMENT_STAGE1.md), [WINDOWS_DEVELOPMENT_GOTCHAS.md](WINDOWS_DEVELOPMENT_GOTCHAS.md)

## Purpose And Scope

This guide covers the operator-owned setup work that happens before live
capital: account setup, wallet architecture, funding flow, CLOB credential
derivation, minimum balances and reserves, tax recordkeeping, and the machine
checklist for the Canadian partner host.

Use this guide to prepare the operator environment. Use
`docs/OPERATOR_QUICKSTART.md` for the actual PolyTool command flow, and use
`docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md` only when all gates and the 72 hour
Stage 0 paper-live run are already complete.

## Repo Guardrails

- No live capital before: replay -> sweep -> shadow -> dry-run -> Stage 0
  paper-live (72 hours) -> Stage 1 live capital.
- Cold-wallet capital never belongs on a VPS and never belongs in `.env`.
- The hot wallet is a separate trading wallet and should hold only the current
  stage capital.
- The live runbook expects `PK` and, once derived, `CLOB_API_KEY`,
  `CLOB_API_SECRET`, and `CLOB_API_PASSPHRASE`.
- Grafana dashboards and operator alerts should be active before any Stage 1
  session.

## 1. Account Setup Checklist

Work through this in order. Do not fund the hot wallet until the list is
complete.

1. Confirm which platform is primary for first live deployment.
   Operator Decision Needed: `Primary platform = <Polymarket on Canadian host | Kalshi backup | other approved path>`
2. Create the operator account on the chosen platform and complete KYC if the
   platform requires it.
3. Confirm access from the intended trading machine before sending capital.
   The v5 roadmap assumes Polymarket access may need the Canadian partner
   machine rather than a US host.
4. Create a backup account path if the primary path is blocked.
   The roadmap names Kalshi as the jurisdiction-safe backup.
5. Choose the fiat on-ramp exchange that will be used to buy USDC.
   Operator Decision Needed: `Primary exchange = <fill in>`
6. Decide who will own the operational tax records and monthly review.
   Operator Decision Needed: `Tax owner / accountant = <fill in>`
7. Decide which machine is the live host.
   Operator Decision Needed: `Live host = <Canadian partner workstation | VPS | other>`

## 2. Wallet Architecture

The roadmap requires two wallets.

### Cold Wallet

- Purpose: long-term capital storage.
- Rules from v5:
  - Never on VPS.
  - Never in `.env`.
  - Use it to hold capital that is not actively allocated to the current stage.
- Operator Decision Needed: `Cold wallet product / custody method = <hardware wallet / multisig / other>`

### Hot Wallet

- Purpose: live trading only.
- Rules from v5:
  - Separate from the cold wallet.
  - Funded with current-stage capital only.
  - Used to derive CLOB API credentials.
  - USDC allowance should be capped at `2x` current-stage capital.
- Operator Decision Needed: `Hot wallet software / device = <fill in>`
- Operator Decision Needed: `Hot wallet address = <fill in after creation>`
- Operator Decision Needed: `Allowance review cadence = <daily / per deployment / other>`

### Practical Wallet Flow

1. Create the cold wallet first.
2. Create the hot wallet second.
3. Record both addresses in the operator ledger.
4. Keep the hot-wallet private key out of chat logs, docs, screenshots, and
   committed files.
5. Copy only the hot-wallet private key into `.env` on the live host when you
   are ready to derive CLOB credentials.
6. Fund the hot wallet only with the stage capital you are willing to risk for
   the current stage.

## 3. Fiat -> Exchange -> USDC -> Polygon -> Polymarket Flow

The roadmap explicitly calls for documenting the exact flow and recording the
real fees and timing from the operator's own run.

### Funding Steps

1. Send fiat to the chosen exchange account.
2. Buy USDC on that exchange.
3. Withdraw the USDC on the Polygon network to the hot-wallet address.
4. Confirm the USDC arrives in the hot wallet before connecting that wallet to
   Polymarket.
5. Connect the hot wallet to Polymarket and complete the smallest practical
   deposit / approval test before larger transfers.
6. Record the actual exchange fee, network fee, and elapsed time for that run.
   Do not use guessed numbers in the ledger.

### Withdrawal / Return Path

1. Withdraw or redeem proceeds back to the hot wallet.
2. Move realized profit that is not staying in stage capital out of the hot
   wallet on the operator's chosen cadence.
3. Send reserves or excess capital back to the cold wallet or to the exchange
   for off-platform storage.
4. Record the actual fees and timing for the return path too.

### Funding Ledger Template

| Step | What to record |
|------|----------------|
| Fiat -> exchange | date/time, amount, exchange used, any exchange funding fee |
| Exchange -> USDC | purchase time, amount of USDC received, trading fee if any |
| Exchange -> Polygon hot wallet | network used, destination wallet, withdrawal fee, tx id |
| Hot wallet -> Polymarket | approval/deposit time, amount, tx id |
| Withdrawal / return | amount returned, destination, fees, completion time |

- Operator Decision Needed: `Primary fiat source account = <fill in>`
- Operator Decision Needed: `Primary exchange account owner = <fill in>`
- Operator Decision Needed: `Where excess USDC returns after each cycle = <cold wallet / exchange / other>`

## 4. Derive CLOB API Credentials With `py-clob-client`

The repo already contains the credential bootstrap helper at
`packages/polymarket/simtrader/execution/wallet.py`. That helper reads `PK`
from the environment and prints the derived `CLOB_API_*` values.

### Prepare `.env`

1. Copy `.env.example` to `.env` if `.env` does not already exist.
2. Fill only the hot-wallet private key first:

```env
PK=replace_with_hot_wallet_private_key_hex_no_0x
```

3. Leave the `CLOB_API_KEY`, `CLOB_API_SECRET`, and `CLOB_API_PASSPHRASE`
   placeholders empty until the derivation step completes.
4. Load `PK` into the current shell before running the helper.
   `wallet.build_client()` reads environment variables directly; it does not
   read `.env` on its own.

Example:

```powershell
$env:PK = "replace_with_hot_wallet_private_key_hex_no_0x"
```

### Install The Client If Needed

`wallet.py` raises an import hint if `py_clob_client` is missing.

```powershell
pip install py-clob-client
```

### Run The Repo Helper

From the repo root, in the same shell where `PK` is already loaded:

```powershell
@'
from packages.polymarket.simtrader.execution import wallet
client = wallet.build_client()
wallet.derive_and_print_creds(client)
'@ | python -
```

Expected result: the helper prints three lines you must store privately:

- `CLOB_API_KEY=...`
- `CLOB_API_SECRET=...`
- `CLOB_API_PASSPHRASE=...`

### Finish The Setup

1. Paste the printed values into `.env`.
2. Load all four values into the shell you will use for live commands.
   The live path expects environment variables to be present at runtime.
3. Keep all four values (`PK` plus the three `CLOB_API_*` values) on the live
   host only.
4. Do not attempt `simtrader live --live` until this step is done.

If `PK` is missing, the helper raises a clear `KeyError`. If
`py_clob_client` is missing, it prints the `pip install py-clob-client` hint.

## 5. Minimum Balances And Reserves

The roadmap calls out gas reserve, withdrawal buffer, tax reserve, and stage
capital discipline. Some amounts are repo rules; some are operator choices.

### Stage Capital

- Stage 0 paper-live capital: `$0`, with a minimum 72 hour run before Stage 1.
- Roadmap capital progression allows Stage 1 micro funding in the `$50-$500`
  range.
- The Stage 1 market-maker examples in the quickstart and live runbook use
  `$500 USDC` with these defaults:
  - `max-position-usd 500`
  - `daily-loss-cap-usd 100`
  - `max-order-usd 200`
  - `inventory-skew-limit-usd 400`
- The v5 risk table also sets `max total notional = 80% of USDC balance`.

Repo inference: if you keep the default Stage 1 `max-position-usd 500`, the hot
wallet balance should be higher than `$500` or the 80% total-notional rule will
bind immediately. The repo does not pick that exact pre-fund amount for you.

### Reserve Checklist

| Reserve bucket | Repo-backed rule | Operator fill-in |
|----------------|------------------|------------------|
| Trading capital | Only current-stage capital belongs in the hot wallet | `Stage amount = <fill in>` |
| Polygon gas reserve | Keep a dedicated gas reserve for approvals, deposits, withdrawals, and redemptions | `MATIC reserve = <fill in>` |
| Withdrawal buffer | Keep uncommitted balance available so exits do not require emergency refunding | `USDC buffer = <fill in>` |
| Tax reserve | Move `30%` of realized profit out of trading capital | `Tax account / wallet = <fill in>` |
| Compute reserve | Route `20%` of realized profit to infra / API / VPS budget | `Compute budget account = <fill in>` |
| USDC allowance cap | Limit allowance to `2x` current-stage capital | `Allowance cap review result = <fill in>` |

## 6. Capital Allocation Rule After Profit

The v5 roadmap sets this post-profit rule:

- `50%` reinvest into trading capital
- `30%` move to tax reserve
- `20%` move to compute / infrastructure

Practical operating loop:

1. Close the accounting period you use for review.
2. Calculate realized profit for that period.
3. Move `30%` to the tax reserve before increasing live size.
4. Move `20%` to the compute / infrastructure bucket.
5. Reinvest only the remaining `50%`.

- Operator Decision Needed: `Allocation cadence = <weekly / monthly / other>`
- Operator Decision Needed: `Where the 30% tax reserve is held = <fill in>`
- Operator Decision Needed: `Where the 20% compute reserve is held = <fill in>`

## 7. Tax Tracking Requirements

The roadmap requirement is explicit: every trade must be logged with timestamps
and cost basis. This guide is operational guidance only, not tax or legal
advice.

### Minimum Fields To Capture

Record these for every deposit, withdrawal, trade, fill, redemption, fee, and
rebate event:

| Field | Why it matters |
|------|----------------|
| Timestamp | Required for ordering, reconciliation, and period reporting |
| Time zone used for reporting | Prevents ambiguity between UTC and local time |
| Wallet used | Separates cold-wallet transfers from hot-wallet trading |
| Platform / exchange | Distinguishes exchange trades, bridge moves, and Polymarket fills |
| Market slug / asset id / token id | Identifies the exact market instrument |
| Side and quantity | Basic trade reconstruction |
| Price and notional | Needed for cost basis and proceeds |
| Fees or rebates | Needed for net result |
| Gas spend / tx hash | Needed for on-chain reconciliation |
| Resulting inventory / position | Helps validate open-vs-closed state |
| Funding source or destination | Ties deposits and withdrawals back to the cash ledger |

### Daily / Session Close Checklist

1. Archive the session date, release commit hash, and any incidents.
2. Review fills, cancels, rejects, and realized PnL.
3. Confirm loss-cap and inventory-skew compliance for the session.
4. Reconcile hot-wallet balance changes against the funding ledger.
5. Move any planned tax or compute reserve transfers on the chosen cadence.

- Operator Decision Needed: `Primary tax ledger location = <spreadsheet / accounting system / other>`
- Operator Decision Needed: `Who reconciles daily session records = <fill in>`
- Operator Decision Needed: `Reporting time zone = <UTC / local zone / both>`

## 8. Canadian Partner Machine Setup Checklist

This is the minimum practical checklist for the Canadian partner machine the
roadmap expects to host the live bot.

1. Install prerequisites:
   - Python `3.11+`
   - Git
   - Docker Desktop
2. Log into a normal Windows user account that has Docker Desktop access.
   If the machine is Windows, also keep
   `docs/WINDOWS_DEVELOPMENT_GOTCHAS.md` open during setup.
3. Clone the repo and move to the intended release branch or commit for the
   session.
4. Create and activate a virtual environment.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

5. Verify the install:

```powershell
python -m polytool --help
```

6. Copy `.env.example` to `.env` and fill only the values you actually know.
   Do not put cold-wallet credentials in this file.

```powershell
Copy-Item .env.example .env -ErrorAction SilentlyContinue
```

7. Start the local services and confirm they are healthy:

```powershell
docker compose up -d
docker compose ps
```

Expected endpoints from repo docs:

- Grafana: `http://localhost:3000`
- ClickHouse: `http://localhost:8123`

8. Verify the machine can reach the market-data path:

```powershell
python -m polytool market-scan --top 5
```

9. Verify the dry-run path before any live credentials are used:

```powershell
python -m polytool simtrader quickrun --dry-run --list-candidates 5
```

10. Derive and store the hot-wallet CLOB credentials only after the machine has
    passed the checks above.

- Operator Decision Needed: `Canadian host owner = <fill in>`
- Operator Decision Needed: `Host backup / remote-access path = <fill in>`
- Operator Decision Needed: `Primary alert channel = <Telegram / other>`
- Operator Decision Needed: `Polygon RPC provider = <fill in>`

## 9. Open Operator Decisions To Fill Before Funding

Use this as the final pre-funding checklist.

- Operator Decision Needed: `Primary platform`
- Operator Decision Needed: `Primary exchange`
- Operator Decision Needed: `Cold wallet custody method`
- Operator Decision Needed: `Hot wallet product and address`
- Operator Decision Needed: `Stage 1 funding target`
- Operator Decision Needed: `MATIC gas reserve`
- Operator Decision Needed: `USDC withdrawal buffer`
- Operator Decision Needed: `Tax reserve account`
- Operator Decision Needed: `Compute budget account`
- Operator Decision Needed: `Tax ledger / accountant`
- Operator Decision Needed: `Canadian host owner and backup access`
- Operator Decision Needed: `Polygon RPC provider`

## References

- Workflow and command order: [OPERATOR_QUICKSTART.md](OPERATOR_QUICKSTART.md)
- Live trading prerequisites and daily review: [LIVE_DEPLOYMENT_STAGE1.md](runbooks/LIVE_DEPLOYMENT_STAGE1.md)
- Windows host issues and PowerShell-safe patterns: [WINDOWS_DEVELOPMENT_GOTCHAS.md](WINDOWS_DEVELOPMENT_GOTCHAS.md)
