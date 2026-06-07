# Status Deploy Fix

Date: 2026-06-04
Agent: Codex
Scope: Diagnose and fix the deployed Vera `/status` mismatch without touching
kill switch, signing, order/price, risk manager, rate limiter, or denylist logic.

## Files Changed

- `docs/CURRENT_STATE.md` - updated the DR-3 `/status` state with the deploy
  diagnosis, rebuild/restart result, username sidecar verification, and remaining
  Discord-client visual check.
- `docs/dev_logs/2026-06-04_status-deploy-fix.md` - this handoff log.

No source code was edited in this session.

## Diagnosis

`/status` was showing blank usernames and `$0` PnL because the running
`vera-bot` container had stale code.

Evidence:

```text
docker compose ps
NAME                           IMAGE                                 COMMAND                  SERVICE               CREATED       STATUS                    PORTS
polytool-api                   polytool-api                          "uvicorn main:app --…"   api                   2 hours ago   Up 16 minutes (healthy)   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
polytool-clickhouse            clickhouse/clickhouse-server:latest   "/entrypoint.sh"         clickhouse            2 hours ago   Up 17 minutes (healthy)   0.0.0.0:8123->8123/tcp, [::]:8123->8123/tcp, 0.0.0.0:9000->9000/tcp, [::]:9000->9000/tcp
polytool-discovery-scheduler   polytool-discovery-scheduler          "python -m polytool …"   discovery-scheduler   2 hours ago   Up 17 minutes
polytool-grafana               grafana/grafana:11.4.0                "/run.sh"                grafana               2 hours ago   Up 16 minutes (healthy)   0.0.0.0:3000->3000/tcp, [::]:3000->3000/tcp
polytool-ris-scheduler         polytool-ris-scheduler                "python -m polytool …"   ris-scheduler         2 hours ago   Up 17 minutes
polytool-vera-bot              polytool-vera-bot                     "python -m packages.…"   vera-bot              2 hours ago   Up 17 minutes
```

```text
Repo packages/polymarket/discord_bot/status_window.py SHA256:
F953F2613D1D0D85F634AA7C3490B87212CA7CA60F2532A235DD63B2AA1678E2

Running container /app/packages/polymarket/discord_bot/status_window.py:
exists True
sha256 3b43ed118cb2a295076f32532169fd856c198e7b10918413ef3d6d90bfc0347f
has leaderboard loader False
has realized_net_pnl False
has display_name False
```

The artifact mount was present and non-zero, so the data was not absent:

```text
latest /app/artifacts/research/wallet_scan/2026-06-04/e5d83309-e76d-49ff-8c4e-d98028f9a87c/leaderboard.json
entries 5
row 1 identifier '0xa380c504a480f591c7dfbf9944fac3994b9b21ff' username '' realized_net_pnl 885464.776842
```

Conclusion: cause (a), stale running bot code. The username handoff was also
verified separately because the latest pre-fix artifact had empty `username`
values.

## Actions

Rebuilt and recreated only `vera-bot`:

```text
docker compose build vera-bot
...
polytool-vera-bot  Built
```

```text
docker compose up -d vera-bot
Container polytool-vera-bot  Recreate
Container polytool-vera-bot  Recreated
Container polytool-vera-bot  Started
```

Post-restart verification:

```text
docker compose ps vera-bot
NAME                IMAGE               COMMAND                  SERVICE    CREATED          STATUS          PORTS
polytool-vera-bot   polytool-vera-bot   "python -m packages.…"   vera-bot   19 seconds ago   Up 16 seconds
```

```text
docker exec polytool-vera-bot python -c "...hash/status_window checks..."
f953f2613d1d0d85f634aa7c3490b87212ca7ca60f2532a235dd63b2aa1678e2
has leaderboard loader True
has realized_net_pnl True
has display_name True
```

Bot gateway health:

```text
docker logs --tail 120 polytool-vera-bot
2026-06-04 20:10:30,713 INFO vera.bot: Slash commands synced to guild 1411788462142783551 (instant).
2026-06-04 20:10:31,188 INFO discord.gateway: Shard ID None has connected to Gateway (Session ID: 85de464c95c8446b7b677dadd4315487).
2026-06-04 20:10:33,216 INFO vera.bot: Vera is online as VERA#2261 (id=1497296971130474566).
```

The log also showed HTTP 404s from the optional `ris_documents` probe during
local status checks. The returned snapshot still had `degraded=[]` and valid
tiles; no code change was made for that optional logging behavior.

## Username Handoff Verification

First export attempt failed under sandboxed network and wrote zero addresses:

```text
python -m polytool discovery export-leaderboard --top 5 --out artifacts/watchlists/top5.txt
Exported 0 wallet address(es) (requested top 5) to artifacts/watchlists/top5.txt
Connection error: HTTPSConnectionPool(host='data-api.polymarket.com', port=443): ... [WinError 10013] ...
Leaderboard fetch error on page 1: Max retries (3) exceeded for https://data-api.polymarket.com/v1/leaderboard
  Warning: zero addresses written — the leaderboard API returned no entries (check network access to data-api.polymarket.com).
```

Reran with approved network escalation:

```text
python -m polytool discovery export-leaderboard --top 5 --out artifacts/watchlists/top5.txt
Exported 5 wallet address(es) (requested top 5) to artifacts/watchlists/top5.txt
  Username sidecar: artifacts/watchlists/top5.txt.usernames.json (5 name(s); display-only, wallet-scan picks it up automatically)
  Next: python -m polytool wallet-scan --input artifacts/watchlists/top5.txt --extract-dossier
```

Sidecar contents:

```json
{
  "0x6211f97a76ed5c4b1d658f637041ac5f293db89e": "Tiger200",
  "0xa380c504a480f591c7dfbf9944fac3994b9b21ff": "JewishNinja",
  "0xbddf61af533ff524d27154e589d2d7a81510c684": "Countryside",
  "0xbee54d90051720e27921dc6874f02d646ffca636": "downtownfee",
  "0xf8831548531d56ad6a4331493243c447a827cd1f": "Inaccuratestake"
}
```

Ran wallet scan with `.env` loaded:

```text
python -m polytool wallet-scan --input artifacts/watchlists/top5.txt --extract-dossier
Wallet scan complete
Run root: artifacts/research/wallet_scan/2026-06-04/a9fbf46f-a276-46cb-9290-b37a600a2af3
Manifest: artifacts/research/wallet_scan/2026-06-04/a9fbf46f-a276-46cb-9290-b37a600a2af3/wallet_scan_manifest.json
Leaderboard JSON: artifacts/research/wallet_scan/2026-06-04/a9fbf46f-a276-46cb-9290-b37a600a2af3/leaderboard.json
Leaderboard Markdown: artifacts/research/wallet_scan/2026-06-04/a9fbf46f-a276-46cb-9290-b37a600a2af3/leaderboard.md
Per-user results: artifacts/research/wallet_scan/2026-06-04/a9fbf46f-a276-46cb-9290-b37a600a2af3/per_user_results.jsonl
```

Fresh leaderboard verification from the running bot container:

```text
latest /app/artifacts/research/wallet_scan/2026-06-04/a9fbf46f-a276-46cb-9290-b37a600a2af3/leaderboard.json
entries 5
1 identifier= 0xf8831548531d56ad6a4331493243c447a827cd1f wallet_id= 0xf8831548531d56ad6a4331493243c447a827cd1f username= Inaccuratestake display_name= Inaccuratestake pnl= 1259675.749106 positions= 27
2 identifier= 0xa380c504a480f591c7dfbf9944fac3994b9b21ff wallet_id= 0xa380c504a480f591c7dfbf9944fac3994b9b21ff username= JewishNinja display_name= JewishNinja pnl= 885464.776842 positions= 5
3 identifier= 0xbddf61af533ff524d27154e589d2d7a81510c684 wallet_id= 0xbddf61af533ff524d27154e589d2d7a81510c684 username= Countryside display_name= Countryside pnl= -146567.424253 positions= 50
4 identifier= 0x6211f97a76ed5c4b1d658f637041ac5f293db89e wallet_id= 0x6211f97a76ed5c4b1d658f637041ac5f293db89e username= Tiger200 display_name= Tiger200 pnl= -894603.891089 positions= 50
5 identifier= 0xbee54d90051720e27921dc6874f02d646ffca636 wallet_id= 0xbee54d90051720e27921dc6874f02d646ffca636 username= downtownfee display_name= downtownfee pnl= -1807847.38443 positions= 50
```

## Deployed `/status` Payload Verification

This check ran inside the actual `polytool-vera-bot` container, using its real
environment and the same `read_status_snapshot()` path called by the Discord
handler. It is not a unit test.

```text
snap_none False
degraded []
tiles {'in_queue': 0, 'scanned_today': 0, 'pending_review': 0, 'failed': 0}
```

Top-N fields returned by the deployed reader:

```json
[
  {
    "name": "Wallet ID",
    "value": "`0xf883…cd1f`\n`0xa380…21ff`\n`0xbddf…c684`\n`0x6211…b89e`\n`0xbee5…a636`",
    "inline": true
  },
  {
    "name": "Username",
    "value": "Inaccuratestake\nJewishNinja\nCountryside\nTiger200\ndowntownfee",
    "inline": true
  },
  {
    "name": "Net PnL",
    "value": "+$1.3m · 27 pos\n+$885.5k · 5 pos\n-$146.6k · 50 pos\n-$894.6k · 50 pos\n-$1.8m · 50 pos",
    "inline": true
  }
]
```

I could not originate a true Discord slash-command interaction from this
environment. Discord slash commands are user-client initiated; the bot token can
connect/sync/respond but cannot safely invoke `/status` as a user. Final visual
confirmation in Discord remains an operator action.

## Commands Run

- `git status --short` - RC 0; repo was already dirty with many modified and
  untracked files across Docker, docs, Vera, discovery, wallet-scan, and tests.
- `git log --oneline -5` - RC 0; latest commit
  `a2ea5be docs(vault): sync Hermes retirement + Discord notification/bot system`.
- `python -m polytool --help` - RC 0; CLI loaded and listed `wallet-scan`,
  `discovery`, `scan`, SimTrader, RIS, and utility commands.
- `docker compose ps` - RC 0; `polytool-vera-bot` service found.
- `docker exec polytool-vera-bot ...status_window hash...` - RC 0; proved stale
  hash before rebuild and current hash after rebuild.
- `docker compose build vera-bot` - RC 0; `polytool-vera-bot  Built`.
- `docker compose up -d vera-bot` - RC 0; `polytool-vera-bot  Started`.
- `python -m polytool discovery export-leaderboard --top 5 --out artifacts/watchlists/top5.txt`
  - first RC 1 under sandbox (`WinError 10013`); rerun with network approval RC 0,
  `Exported 5 wallet address(es)`.
- `.env`-loaded `python -m polytool wallet-scan --input artifacts/watchlists/top5.txt --extract-dossier`
  - RC 0; `entries_attempted=5`, `entries_succeeded=5`, `entries_failed=0`.
- `docker logs --tail 120 polytool-vera-bot` - RC 0 with approval; confirmed
  slash sync, gateway connect, and `VERA#2261` online.

No full pytest run was performed because no source code was changed in this
session; the deploy fix was rebuild/restart plus artifact regeneration.

## Decisions

- Did not edit `status_window.py`; the reported symptoms matched old deployed
  code, and hash/content comparison confirmed that.
- Did not touch denylist, kill switch, signing, order/price, risk manager, or
  rate limiter files.
- Did not commit. The operator explicitly required approval before commit.

## Open Questions / Blockers

- Operator should invoke `/status` from the Discord client once to visually
  confirm the live card in-channel. The deployed container payload already shows
  non-zero PnL, real handles, positions, and ClickHouse-backed tiles.
- Optional: the `ris_documents` probe logs HTTP 404 when the table is absent.
  It does not degrade the returned card, but the logging behavior is noisy.

## Codex Review Summary

Tier: skip/reported. This was a deployment and documentation work unit, not an
adversarial source-code review. No Mandatory review files were modified.
