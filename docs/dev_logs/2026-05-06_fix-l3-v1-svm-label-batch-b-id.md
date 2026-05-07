# Fix: L3 v1 SVM Label Batch B Malformed Candidate ID (#82)

**Date:** 2026-05-06  
**Author:** Claude Code  
**Scope:** Doc-only fix. No labels applied, no code changed, no training run.

---

## Files Changed

| File | Change |
|---|---|
| `artifacts/research/svm_filter_label_expansion/label_batch_B.md` | Replaced malformed candidate ID in table row and ALLOW command block |
| `docs/dev_logs/2026-05-06_fix-l3-v1-svm-label-batch-b-id.md` | This dev log |

---

## What Was Fixed

Codex verification (`2026-05-06_codex-verify-l3-v1-svm-label-batches.md`) flagged Batch B row #82 as FAIL: the candidate ID was truncated/malformed, matching zero records in the pending queue.

**Malformed ID (removed):** `c958d1df01636431`  
**Correct full ID (inserted):** `c958d1df0163643d1bcdd4c9a99dd9b98dc688b387ad9310a5b7f0f4a5509d1e`

Title: *Model-based gym environments for limit order book trading*

Two locations were updated in `label_batch_B.md`:

1. **Line 98** — table row column "Candidate ID (prefix)": prefix replaced with full ID  
2. **Line 149** — Director ALLOW copy-paste block: command token replaced with full ID

The Codex review noted the malformed string as `c958d1df01636431` (16 hex chars), which diverges from the actual queue entry at the 15th character (`3` vs `3d`). The correct 16-char prefix would be `c958d1df0163643d`; the fix uses the full 64-char SHA-256 to eliminate any ambiguity.

---

## Commands Run and Output

### Baseline (before fix)

```
python -m polytool research-prefetch-review counts --json
```
```json
{
  "total_queued": 159,
  "pending_unlabeled": 98,
  "labeled_total": 61,
  "labeled_allow": 30,
  "labeled_reject": 31
}
```

```
Get-FileHash -Algorithm SHA256 -LiteralPath 'artifacts\research\svm_filter_labels\labels.jsonl'
```
```
SHA256  3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2
```

### Verification (after fix)

Grep for malformed ID — no matches:
```
Select-String c958d1df01636431 label_batch_B.md  → (no output)
```

Grep for full corrected ID — two matches (table row + command):
```
label_batch_B.md:98:  | 82 | `c958d1df0163643d1bcdd4c9a99dd9b98dc688b387ad9310a5b7f0f4a5509d1e` | ...
label_batch_B.md:149: python -m polytool research-prefetch-review label c958d1df0163643d1bcdd4c9a99dd9b98dc688b387ad9310a5b7f0f4a5509d1e allow
```

Post-fix counts — unchanged:
```json
{
  "total_queued": 159,
  "pending_unlabeled": 98,
  "labeled_total": 61,
  "labeled_allow": 30,
  "labeled_reject": 31
}
```

Post-fix labels.jsonl SHA256 — unchanged:
```
SHA256  3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2
```

---

## Label Status

Labels remain **unapplied**. `labeled_total = 61` before and after this fix. `labels.jsonl` was not touched.

---

## Next Recommended Step

Batch B is now clean. Director may proceed with manual labeling using the corrected packets:

1. Apply Batch A ALLOW block (21 commands)
2. Apply Batch A REJECT block (26 commands)
3. Apply Batch B ALLOW block (23 commands, now with correct #82 ID)
4. Apply Batch B REJECT block (25 commands)
5. Run `python -m polytool research-prefetch-review counts --json` to verify projected totals (labeled_total → 109 after A+B, or 156 if all 95 non-pending are applied)
6. Director may then proceed toward L3 enforce unlock once ≥150 labels are confirmed
