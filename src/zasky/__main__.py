"""Command-line entry point for the single Zasky process."""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys

from pydantic import ValidationError

from zasky.app import ZaskyApp
from zasky.config import Settings, load_settings
from zasky.logging_config import configure_logging


def _field_names(error: ValidationError) -> str:
    names: set[str] = set()
    for item in error.errors():
        location = item.get("loc", ())
        if location:
            names.add(str(location[0]))
    return ", ".join(sorted(names)) or "unknown field"


async def _run(settings: Settings) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # pragma: no cover - non-POSIX
            pass
    app = ZaskyApp(settings)
    await app.run_forever(stop)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Zasky")
    parser.add_argument(
        "--env-file",
        default=None,
        help="Protected environment file; defaults to ZASKY_ENV_FILE or .env",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate configuration and exit without connecting",
    )
    args = parser.parse_args()

    configure_logging("INFO")
    try:
        settings = load_settings(args.env_file)
    except FileNotFoundError as exc:
        print(f"Configuration file not found: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    except ValidationError as exc:
        print(
            f"Configuration invalid: {_field_names(exc)}",
            file=sys.stderr,
        )
        raise SystemExit(2) from None

    configure_logging(settings.log_level)

    if args.check:
        print("Configuration valid.")
        return

    try:
        asyncio.run(_run(settings))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
