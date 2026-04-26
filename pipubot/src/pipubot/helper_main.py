from __future__ import annotations

import logging

from pipubot.runtime.helper_runtime_setup import build_helper_runtime


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def main() -> None:
    _setup_logging()
    runtime = build_helper_runtime()
    runtime.run()


if __name__ == "__main__":
    main()
