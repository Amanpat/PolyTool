---
title: Ris Marker Gpu Failure Diagnosis
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-03_ris-marker-gpu-failure-diagnosis.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# RIS Marker GPU Failure Diagnosis

Date: 2026-05-03  
Scope: L1 Marker GPU Docker validation — root cause investigation and fix  
Status: Root cause identified and fixed; Docker rebuild blocked by Docker Desktop crash during session

---

## Problem Statement

`research-parser-benchmark --parsers marker` returned `marker_failed` for all 3 papers with `body_length=0` and blank `note` column. Docker GPU passthrough confirmed working (`nvidia-smi` shows RTX 2070 Super). Root cause unknown.

---

## Diagnostic Commands Run

### 1. GPU/torch availability inside ris-scheduler-gpu

```
docker compose --profile ris-gpu run --rm ris-scheduler-gpu python -c \
  "import torch; print('torch:', torch.__version__); print('cuda_available:', torch.cuda.is_available()); print('device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
```

**Result:**
```
torch: 2.11.0+cu130
cuda_available: True
device: NVIDIA GeForce RTX 2070 SUPER
```

GPU passthrough is working. Torch sees the GPU.

### 2. Marker module import

```
docker compose --profile ris-gpu run --rm ris-scheduler-gpu python -c \
  "import marker; print('marker module:', marker); print('marker file:', marker.__file__)"
```

**Result:**
```
marker module: <module 'marker' (<_frozen_importlib_external.NamespaceLoader object at ...>)>
marker file: None
```

marker is a namespace package (no `__init__.py`), which is normal for marker-pdf 1.x. Not a blocking issue by itself.

### 3. marker API import check

```
docker compose --profile ris-gpu run --rm ris-scheduler-gpu python -c "
from marker.converters.pdf import PdfConverter; print('PdfConverter: OK', PdfConverter)
from marker.models import create_model_dict; print('create_model_dict: OK')
from marker.output import text_from_rendered; print('text_from_rendered: OK')"
```

**Result:**
```
PdfConverter FAIL: Could not import module 'PreTrainedModel'. Are this object's requirements defined correctly?
create_model_dict FAIL: cannot import name 'PreTrainedModel' from 'transformers' (...)
text_from_rendered: OK
```

`PdfConverter` and `create_model_dict` both fail on import. `transformers.PreTrainedModel` cannot be loaded.

### 4. Package version audit + PreTrainedModel traceback

```
docker compose --profile ris-gpu run --rm ris-scheduler-gpu python -c "
import importlib.metadata as m
print('transformers:', m.version('transformers'))
print('torch:', m.version('torch'))
print('torchvision:', m.version('torchvision'))
print('marker-pdf:', m.version('marker-pdf'))
import transformers
from transformers import PreTrainedModel"
```

**Result (abbreviated traceback):**
```
transformers: 4.57.6
torch: 2.11.0
torchvision: 0.21.0+cu124
marker-pdf: 1.10.2

ModuleNotFoundError: Could not import module 'PreTrainedModel'.
  [from transformers/__init__.py → modeling_utils.py →
   loss_d_fine.py → image_transforms.py → image_utils.py →
   torchvision.transforms → torchvision/__init__.py →
   torchvision._meta_registrations → @torch.library.register_fake("torchvision::nms") →
   RuntimeError: operator torchvision::nms does not exist]
```

---

## Root Cause

**torch/torchvision CUDA version mismatch.**

| Package | Installed | Should be |
|---|---|---|
| torch | 2.11.0+cu130 (CUDA 13.0) | 2.11.0+cu130 |
| torchvision | 0.21.0+cu124 (CUDA 12.4, companion to torch 2.6.0) | 0.26.0+cu130 |

**How the mismatch occurred:**

1. Dockerfile.ris Layer 2 installed `torch torchvision --index-url https://download.pytorch.org/whl/cu124`, giving torch 2.6.0+cu124 + torchvision 0.21.0+cu124.
2. Dockerfile.ris Layer 3 installed `.[ris,...]` which includes `marker-pdf>=1.0`. marker-pdf 1.10.2 requires `torch>=2.7.0`.
3. pip found torch 2.11.0+cu130 in the BuildKit pip cache (populated by a previous Docker build or session), and upgraded torch to satisfy the `>=2.7.0` requirement.
4. torchvision was NOT upgraded — it stayed at 0.21.0+cu124 (companion to torch 2.6.0, CUDA 12.4).
5. When transformers tried to import, it imported torchvision, which tried to register `torchvision::nms` against the installed torch C library. The cu130-compiled `torch` and cu124-compiled `torchvision` share incompatible libtorch ABIs → operator registration fails → `PreTrainedModel` import fails → `PdfConverter` / `create_model_dict` fail → every paper returns `marker_failed`.

**Secondary bug found (benchmark key mismatch):**

`research_parser_benchmark.py` was reading `meta.get("fallback_reason", "")` for the note column. But `_marker_production_extract()` in `fetchers.py` returns key `"failure_reason"` (not `"fallback_reason"`). This caused the note column to always be blank for `marker_failed` results, hiding all diagnostic information. This is why the benchmark showed no useful note even when Marker was failing with an explicit error.

---

## Files Changed

### `Dockerfile.ris` (root cause fix)

Layer 2 changed from:
```dockerfile
pip install torch torchvision \
    --index-url https://download.pytorch.org/whl/cu124
```

To:
```dockerfile
pip install "torch==2.11.0+cu130" "torchvision==0.26.0+cu130" \
    --index-url https://download.pytorch.org/whl/cu130
```

Pins both packages to the exact CUDA-consistent pair. marker-pdf 1.10.2 finds torch 2.11.0 already installed in Layer 3 and does not upgrade. torchvision 0.26.0+cu130 is the correct companion to torch 2.11.0+cu130.

### `tools/cli/research_parser_benchmark.py` (benchmark diagnostics fix)

- Added `failure_reason: str` field to `ParserResult` dataclass (separate from `fallback_reason`)
- Fixed key read: now reads `meta.get("failure_reason", "")` for marker_failed and `meta.get("fallback_reason", "")` for pdfplumber_fallback separately
- Added `--verbose` flag: shows full failure_reason/error without 40-char truncation; captures full Python traceback for outer exceptions
- Note column now shows `failure_reason or fallback_reason or error` in priority order
- Added `_get_note()` helper for consistent note extraction

---

## Validation Commands (run after Docker rebuild)

### Step 1: Restart Docker Desktop and rebuild image

```powershell
# Docker Desktop must be running
docker compose --profile ris-gpu build --no-cache ris-scheduler-gpu
```

### Step 2: Verify torch+torchvision consistency

```
docker compose --profile ris-gpu run --rm ris-scheduler-gpu python -c "
import torch, torchvision, importlib.metadata as m
print('torch:', m.version('torch'))
print('torchvision:', m.version('torchvision'))
print('torchvision import OK:', torchvision.__version__)
print('cuda:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"
```

Expected: torch 2.11.0+cu130, torchvision 0.26.0+cu130, cuda=True, RTX 2070 Super.

### Step 3: Verify Marker API imports

```
docker compose --profile ris-gpu run --rm ris-scheduler-gpu python -c "
from marker.converters.pdf import PdfConverter; print('PdfConverter: OK')
from marker.models import create_model_dict; print('create_model_dict: OK')
from marker.output import text_from_rendered; print('text_from_rendered: OK')"
```

Expected: all three print OK.

### Step 4: Single-paper benchmark (verbose)

```
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-parser-benchmark \
  --urls 2510.15205 --parsers marker --verbose \
  --output-dir artifacts/benchmark/parser
```

Expected: body_source=marker, body_length >5000.

### Step 5: Three-paper benchmark (only if Step 4 passes)

```
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-parser-benchmark --parsers marker \
  --output-dir artifacts/benchmark/parser
```

### Step 6: Unit tests

```
python -m pytest tests/test_ris_academic_pdf.py tests/test_ris_research_acquire_cli.py -x -q --tb=short
```

---

## Benchmark Result (pre-fix)

All 3 papers → `marker_failed`, body_length=0, note blank (due to key mismatch bug)

## Benchmark Result (post-fix)

Not yet run — Docker Desktop crashed during rebuild. Manual restart required.

---

## L1 Status

**BLOCKED** pending Docker rebuild after Desktop restart.

Root cause is identified and the fix is in place in `Dockerfile.ris`. Once the image rebuilds cleanly with `torch==2.11.0+cu130` and `torchvision==0.26.0+cu130`, the Marker import chain should complete and the benchmark should return `body_source=marker` with substantial body text.

L1 is NOT shipped. Do not mark as shipped until Step 4 above shows `body_source=marker` and `body_length > 5000` for at least one paper.

---

## Codex Review

Tier: Recommended (fetchers.py, extractors.py not changed; only benchmark CLI and Dockerfile).  
Issues found: torch/torchvision mismatch (infra), fallback_reason key mismatch (bug).  
Issues addressed: both fixed in this session.
