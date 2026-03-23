# Windows Development Gotchas

See also: [OPERATOR_SETUP_GUIDE.md](OPERATOR_SETUP_GUIDE.md), [OPERATOR_QUICKSTART.md](OPERATOR_QUICKSTART.md), [LIVE_DEPLOYMENT_STAGE1.md](runbooks/LIVE_DEPLOYMENT_STAGE1.md)

## Purpose

This document records Windows-specific issues that have already been observed in
this repo and the practical fixes that worked. It is written for operators and
developers running PolyTool from PowerShell on a Windows host.

## 1. Encoding And Unicode Output Failures

### What was observed

On 2026-03-17, `fetch-price-2min` failed on a Windows cp1252 terminal with:

```text
UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'
```

The direct cause was a Unicode right-arrow character in CLI output. The
repo fix was to replace that arrow with ASCII `->`.

### Practical rule

Prefer ASCII-only CLI-visible text on Windows. In practice, that means:

- Prefer `->` over Unicode arrows.
- Prefer `-` over decorative bullets.
- Prefer plain ASCII quotes when pasting commands into PowerShell.

### What to do when it happens

1. If a command crashes with `UnicodeEncodeError` and the traceback mentions
   `encodings/cp1252.py`, suspect terminal encoding first.
2. Check the command output or the script text for non-ASCII arrows, bullets,
   or symbols.
3. Replace the offending symbol with ASCII and rerun.
4. If you are writing new CLI-visible output in repo code, keep it ASCII.

Repo note: not every Unicode character fails on cp1252, but ASCII-only output
is the safest Windows operating rule.

## 2. Docker Desktop + WSL2: Sandbox Account vs Real Windows User

### What was observed

On 2026-03-18, Docker Desktop looked broken from the Codex sandbox account
because these commands failed with access denied:

- `docker version`
- `docker info`
- `docker compose ps`
- `wsl --status`
- `wsl -l -v`

The same checks succeeded immediately from the real Windows user account. The
problem was account context, not a dead Docker engine.

### Symptom to recognize

If you see errors like:

```text
open //./pipe/dockerDesktopLinuxEngine: Access is denied
```

do not assume Docker Desktop itself is down yet.

### What to do

1. In the failing shell, run:

```powershell
whoami
docker version
docker info
docker compose ps
wsl --status
wsl -l -v
```

2. Open a normal PowerShell session as the real Windows user and run the same
   commands again.
3. If the real-user shell succeeds but the sandboxed shell fails, treat it as a
   permissions boundary.
4. Continue Docker and WSL operations from the real-user shell.
5. Only treat Docker Desktop as unhealthy if the real-user shell fails too.

### Practical rule

When Windows Docker diagnostics disagree between shells, trust the real Windows
user check over the sandbox check.

## 3. Path Separators And Quoting

### What was observed

The repo has already hit a Windows path bug: a test compared a path as a raw
string and failed because Windows returned backslashes while the expected string
used forward slashes.

The repo also has explicit path-normalization rules in places where paths are
serialized, for example `Path.as_posix()` in LLM bundle coverage paths.

### Practical rules

- In Python or tests, compare `Path(...)` objects, not raw stringified paths.
- In serialized output or docs that need stable path text, prefer forward
  slashes.
- In PowerShell, always quote paths that contain spaces.
- In PowerShell, quote `@user` values.
- Do not use bash-style `\"` escaping for JSON arguments.

### Safe examples

Quote paths with spaces:

```powershell
python -m polytool close-benchmark-v1 --pmxt-root "D:\Coding Projects\Polymarket\PolyToolData\raw\pmxt_archive"
```

Quote `@` handles:

```powershell
python -m polytool scan --user "@example"
```

For JSON arguments, use single quotes or `ConvertTo-Json`:

```powershell
$cfg = @{ buffer = 0.01; max_size = 25 } | ConvertTo-Json -Compress
python -m polytool simtrader quickrun --strategy-config-json $cfg
```

## 4. `.env` Encoding And Line Endings

### What the repo does

The repo's `.env` loaders open `.env` with `encoding="utf-8"` and do not use
`utf-8-sig` for that file. By contrast, some JSON readers in the SimTrader path
explicitly accept UTF-8 BOM.

### Practical rule

Save `.env` as plain UTF-8 without BOM.

### Why this matters

Repo inference: if `.env` starts with a UTF-8 BOM, the first key can be read
with that hidden BOM prefix instead of the expected key name. That can make the
first variable appear "missing" even though it is present in the file.

### Line endings

Repo inference: normal Windows CRLF line endings are acceptable because the
loaders strip surrounding whitespace from each line. The higher-risk issue is
encoding and hidden BOM, not CRLF by itself.

### Safe `.env` habits

- Start from `.env.example`.
- Keep one `KEY=value` pair per line.
- Avoid smart quotes and rich-text editors.
- If a key like `PK` or `CLICKHOUSE_PASSWORD` seems ignored, recreate `.env`
  from `.env.example` and save it again as UTF-8 without BOM.

## 5. PowerShell-Safe Command Tips

- Run commands from the repo root unless a doc says otherwise.
- Use the PowerShell-native copy command from repo docs:

```powershell
Copy-Item .env.example .env -ErrorAction SilentlyContinue
```

- Quote all Windows paths that contain spaces.
- Quote `@handle` values.
- Prefer one-line commands, PowerShell here-strings, or backtick continuation
  from repo docs instead of bash-only syntax.
- For JSON CLI arguments, use single quotes or `ConvertTo-Json`.
- For Docker and WSL checks, use a normal real-user PowerShell session.

## 6. Short Troubleshooting Checklist

1. `UnicodeEncodeError` with `cp1252`:
   - Replace non-ASCII symbols with ASCII and rerun.
2. `dockerDesktopLinuxEngine` access denied:
   - Run `whoami`, then repeat the Docker and WSL checks from a real-user
     PowerShell session.
3. Wrong output folder or bad user routing:
   - Quote `--user "@name"` exactly.
4. JSON argument parsing behaves strangely:
   - Stop using bash escaping. Use single quotes or `ConvertTo-Json`.
5. `.env` values seem missing:
   - Recreate `.env` as UTF-8 without BOM.
6. Host-side ClickHouse connection fails on Windows:
   - Confirm the host uses `localhost`, not Docker service name `clickhouse`.

## References

- Operator-owned setup decisions: [OPERATOR_SETUP_GUIDE.md](OPERATOR_SETUP_GUIDE.md)
- End-to-end CLI flow: [OPERATOR_QUICKSTART.md](OPERATOR_QUICKSTART.md)
- Live run prerequisites: [LIVE_DEPLOYMENT_STAGE1.md](runbooks/LIVE_DEPLOYMENT_STAGE1.md)
