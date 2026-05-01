"""Production ASGI server entrypoint."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    """Start the API server using the platform-provided port when available."""
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "alphalens.api.main:app",
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
