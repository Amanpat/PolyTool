# Deprecated

`services/studio` is no longer a standalone Studio implementation.

The canonical Studio backend+UI lives at:

- `packages/polymarket/simtrader/studio/app.py`
- `packages/polymarket/simtrader/studio/static/index.html`

Use:

```bash
python -m polytool simtrader studio
```
