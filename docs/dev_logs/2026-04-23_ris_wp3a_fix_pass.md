---
date: 2026-04-23
slug: ris_wp3a_fix_pass
work_packet: WP3-A (fix pass)
phase: RIS Phase 2A
status: complete
---

# WP3-A Fix Pass: JS Newline Escaping in Parse Nodes

## File Changed

`infra/n8n/workflows/ris-unified-dev.json`

Only the `jsCode` parameter of the six targeted parse nodes was modified. Node count (76),
connection count (56), and all other node fields are unchanged.

## Root Cause

The original WP3-A patch wrote `stdout.split('\n')` into the JSON `jsCode` string.

In JSON, `\n` is the escape sequence for a literal newline character (U+000A). When n8n
(or any JSON parser) decodes the string, that `\n` becomes an actual line-feed inside the
JS source text. The result is:

```js
const lines = stdout.split('
');   // ← literal LF inside single-quoted string → JS SyntaxError
```

JavaScript single-quoted string literals cannot contain unescaped newlines. This caused
`new Function(jsCode)` to throw `Invalid or unexpected token` for all six nodes.

## Fix

Changed `split('\n')` to `split('\\n')` in the JSON source (i.e., in the Python string that
`json.dump` serialises). After JSON decode, n8n sees the valid JS escape sequence:

```js
const lines = stdout.split('\n');   // '\n' = JS escape for newline ✓
```

The structural newlines between JS statements — also encoded as `\n` in the JSON string —
decode to actual newlines in the source and are syntactically fine (they are whitespace
between statements). Only the `\n` inside the string literal argument to `.split()` required
fixing.

The fix was applied via a Python `json.load` / `str.replace` / `json.dump` round-trip.
`ensure_ascii=False` preserves any non-ASCII content; `newline='\n'` keeps Unix line endings.

## Validation Commands and Results

```bash
python -c "import json; d=json.load(open('infra/n8n/workflows/ris-unified-dev.json',encoding='utf-8')); \
  print('json_valid=1 nodes=' + str(len(d['nodes'])) + ' connections=' + str(len(d.get('connections',{}))))"
# json_valid=1 nodes=76 connections=56

node - <<'EOF'
const fs = require('fs');
const data = JSON.parse(fs.readFileSync('infra/n8n/workflows/ris-unified-dev.json','utf8'));
const targets = ['s2-parse','s3-parse','s4-parse','s5-parse','s6-parse','s7-parse'];
let failures = 0;
for (const n of data.nodes) {
  if (targets.includes(n.id)) {
    try { new Function(n.parameters.jsCode); console.log(n.id + '=syntax_ok'); }
    catch(e) { failures++; console.log(n.id + '=syntax_error:' + e.message); }
  }
}
process.exitCode = failures ? 1 : 0;
EOF
# s2-parse=syntax_ok
# s3-parse=syntax_ok
# s4-parse=syntax_ok
# s5-parse=syntax_ok
# s6-parse=syntax_ok
# s7-parse=syntax_ok

python -m polytool --help  # exit=0, CLI loads cleanly
```

## WP3-A Status

**Complete.** All six parse nodes (`s2-parse` through `s7-parse`) are now valid JavaScript,
the workflow file is well-formed JSON, and the CLI is unaffected.
