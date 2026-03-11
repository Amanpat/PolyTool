"""Deprecated Studio entrypoint.

Use the canonical Studio entrypoint instead:
    python -m polytool simtrader studio
"""

from __future__ import annotations

from packages.polymarket.simtrader.studio.app import create_app

app = create_app()


if __name__ == "__main__":
    import uvicorn

    print(
        "[deprecated] services.studio.serve now proxies the canonical "
        "packages.polymarket.simtrader.studio.app entrypoint."
    )
    uvicorn.run(
        "services.studio.serve:app",
        host="127.0.0.1",
        port=8765,
        reload=True,
    )
