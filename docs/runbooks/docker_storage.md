# Docker Storage Management Runbook

Relevant context: The RIS GPU image (`Dockerfile.ris`) bundles CUDA torch 2.11.0+cu130
(~2.5 GB installed) plus marker-pdf and its transformers/timm/surya-ocr dependency tree
(~2 GB). The resulting runtime image is ~5–6 GB. Multiple failed rebuilds accumulate
dangling images, and BuildKit cache compounds the total. WSL2 ext4 virtual disks grow but
never shrink automatically after `docker prune`. This runbook exists because Docker + WSL
grew to ~73 GB and exhausted C: during L1 Marker GPU validation (2026-05-03).

---

## Expected Image Sizes

| Image | Extras installed | Approx. size |
|---|---|---|
| `Dockerfile` (CPU, api/ris-scheduler) | ris, mcp, simtrader, historical, historical-import, live | ~1.2–1.8 GB |
| `Dockerfile.bot` (pair-bot) | live, simtrader | ~350–500 MB |
| `Dockerfile.ris` (GPU scheduler) | ris, mcp, simtrader, historical, historical-import, live + CUDA torch | ~5–6 GB |

BuildKit pip cache on disk (separate from images): ~3–4 GB for the CUDA torch wheel.

**Minimum free space before GPU rebuild**: ≥ 15 GB on the drive hosting Docker WSL data
(typically C:). Rebuild + build cache + model weights can peak at 10–12 GB.

---

## 1. Audit (read-only)

Run these before any cleanup to understand current state.

```powershell
# Docker-level summary
docker system df

# Verbose breakdown: which images, containers, build cache entries
docker system df -v

# Image list with sizes
docker image ls

# Dangling (unreferenced) images only
docker image ls -f dangling=true

# Build cache size
docker builder du

# Named volumes
docker volume ls

# WSL distribution disk usage (approximate inside container)
wsl -d docker-desktop df -h /
```

---

## 2. Safe Cleanup (non-destructive to operator data)

These commands do not delete named volumes or mounted host data.

```powershell
# Remove dangling (untagged) images — safe, just build leftovers
docker image prune -f

# Remove stopped containers — safe if nothing is being debugged
docker container prune -f

# Remove unused networks — safe
docker network prune -f

# Remove build cache older than 24h, keep 5 GB of recent cache
docker builder prune --keep-storage 5GB --filter until=24h

# Combined safe prune (no volumes)
docker system prune -f
```

After any prune, re-run `docker system df` to confirm the expected reduction.

---

## 3. Unsafe Cleanup — Requires Operator Confirmation

**Do NOT run these without explicit operator approval. They delete named volumes.**

```powershell
# WARNING: deletes clickhouse_data, grafana_data, n8n_data volumes
docker system prune --volumes -f

# WARNING: deletes a specific named volume
docker volume rm clickhouse_data
```

Model weights in `~/.cache/datalab` are host-mounted, not in Docker volumes — they are
NOT touched by `docker system prune --volumes`. Only the ClickHouse, Grafana, and n8n
named volumes are at risk.

---

## 4. Compact WSL2 Disk After Cleanup

WSL2 uses a virtual ext4 disk that grows but does not shrink automatically. After a large
Docker prune, the `ext4.vhd` file still occupies the same space on C: until compacted.

```powershell
# Step 1: shut down all WSL distributions to release file locks
wsl --shutdown

# Step 2: find the ext4.vhd location (run in PowerShell as admin if needed)
# Common paths:
#   C:\Users\<user>\AppData\Local\Docker\wsl\data\ext4.vhd
#   C:\Users\<user>\AppData\Local\Docker\wsl\disk\docker_data.vhd
Get-ChildItem "$env:LOCALAPPDATA\Docker" -Recurse -Force -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in @('.vhd','.vhdx') } | Select-Object FullName, @{N='SizeGB';E={[math]::Round($_.Length/1GB,2)}}

# Step 3: compact the VHD (PowerShell, run as Administrator)
# Replace the path with the actual ext4.vhd found above.
$vhd = "C:\Users\patel\AppData\Local\Docker\wsl\data\ext4.vhd"
$diskpart = @"
select vdisk file="$vhd"
attach vdisk readonly
compact vdisk
detach vdisk
exit
"@
$diskpart | diskpart
```

Alternatively use Optimize-VHD if Hyper-V tools are installed:
```powershell
Optimize-VHD -Path "C:\Users\patel\AppData\Local\Docker\wsl\data\ext4.vhd" -Mode Full
```

After compaction, restart Docker Desktop.

---

## 5. Move Docker Desktop Disk off C:

If C: is chronically low, move Docker Desktop's WSL data image to D: to prevent future
exhaustion.

**Steps (do once, takes 10–20 min):**

```powershell
# 1. Stop Docker Desktop and shut down WSL
# (Close Docker Desktop from taskbar, then:)
wsl --shutdown

# 2. Export the docker-desktop-data distribution
wsl --export docker-desktop-data "D:\Docker\docker-desktop-data.tar"

# 3. Unregister the existing distribution from C:
wsl --unregister docker-desktop-data

# 4. Re-import to D: (creates a new ext4.vhd under D:\Docker\wsl\data\)
New-Item -ItemType Directory -Force -Path "D:\Docker\wsl\data"
wsl --import docker-desktop-data "D:\Docker\wsl\data" "D:\Docker\docker-desktop-data.tar" --version 2

# 5. (Optional) Remove the exported tar once import is confirmed
Remove-Item "D:\Docker\docker-desktop-data.tar"

# 6. Restart Docker Desktop — it should find docker-desktop-data in the new location
```

Note: the `docker-desktop` distro (kernel/tools) is separate from `docker-desktop-data`
(image storage). Moving `docker-desktop-data` is sufficient and safe.

---

## 6. One-Off GPU Benchmark (Minimal Footprint)

For single-paper diagnostics, avoid starting ClickHouse and other services:

```powershell
# Run only the GPU container, no dependency services, auto-remove on exit
docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu \
  python -m polytool research-parser-benchmark \
  --urls 2510.15205 --parsers marker --verbose \
  --output-dir artifacts/benchmark/parser
```

`--no-deps` skips the `depends_on: clickhouse` dependency, avoiding a 1–2 GB ClickHouse
image pull and container start. Only works if the benchmark command itself does not need
ClickHouse.

---

## 7. GPU Build Best Practices

```powershell
# Build GPU image with BuildKit cache (fast on re-run, deps cached)
docker compose --profile ris-gpu build ris-scheduler-gpu

# Force clean rebuild (no cache — use only when debugging layer issues)
docker compose --profile ris-gpu build --no-cache ris-scheduler-gpu

# After successful build, prune dangling images immediately
docker image prune -f

# After each diagnostic session, prune stopped containers
docker container prune -f

# Weekly: prune build cache older than 48h, keep 5 GB
docker builder prune --keep-storage 5GB --filter until=48h
```

---

## 8. Pre-Build Checklist

Before any GPU rebuild, verify:

```powershell
# 1. How much free space is on C:?
(Get-PSDrive C).Free / 1GB  # Need >= 15 GB

# 2. What is Docker currently using?
docker system df

# 3. Any dangling images to clean first?
docker image ls -f dangling=true

# 4. Is model weight cache on host already downloaded?
Test-Path "$env:USERPROFILE\.cache\datalab"
Get-ChildItem "$env:USERPROFILE\.cache\datalab" -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum | Select-Object @{N='SizeGB';E={[math]::Round($_.Sum/1GB,2)}}
```

If C: has less than 15 GB free:
1. Run safe cleanup (Section 2).
2. Compact WSL disk (Section 4).
3. If still insufficient, move Docker to D: (Section 5).

---

## 9. GPU Validation Resume Steps

After disk is healthy, resume L1 Marker validation:

```powershell
# Step 1: Build GPU image
docker compose --profile ris-gpu build ris-scheduler-gpu

# Step 2: Verify torch+torchvision consistency
docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu python -c "
import torch, torchvision, importlib.metadata as m
print('torch:', m.version('torch'))
print('torchvision:', m.version('torchvision'))
print('cuda:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"

# Expected: torch 2.11.0+cu130, torchvision 0.26.0+cu130, cuda=True, RTX 2070 Super

# Step 3: Verify Marker API imports
docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu python -c "
from marker.converters.pdf import PdfConverter; print('PdfConverter: OK')
from marker.models import create_model_dict; print('create_model_dict: OK')
from marker.output import text_from_rendered; print('text_from_rendered: OK')"

# Step 4: Single-paper benchmark (downloads model weights on first run, ~1-3 GB)
docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu \
  python -m polytool research-parser-benchmark \
  --urls 2510.15205 --parsers marker --verbose \
  --output-dir artifacts/benchmark/parser

# Expected: body_source=marker, body_length > 5000

# Step 5: Three-paper benchmark (only if Step 4 passes)
docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu \
  python -m polytool research-parser-benchmark --parsers marker \
  --output-dir artifacts/benchmark/parser
```

L1 is shipped only when Step 4 shows `body_source=marker` and `body_length > 5000`.
