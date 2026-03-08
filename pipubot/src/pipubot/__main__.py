from __future__ import annotations

from pipubot.runtime.app_factory import PipubotAppFactory
from scripts.reset_database import reset_full_database


def main() -> None:
    reset_full_database()
    PipubotAppFactory.from_env().run()


if __name__ == "__main__":
    main()