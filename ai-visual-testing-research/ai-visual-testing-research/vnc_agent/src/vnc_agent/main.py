"""Application entrypoint for `vnc-agent` console script."""

from __future__ import annotations

from vnc_agent.api.cli import app

# Typer app exposed for setuptools entry point
__all__ = ["app"]


def main() -> None:
    app()


if __name__ == "__main__":
    main()
