from __future__ import annotations

from pipubot.runtime.app_factory import PipubotAppFactory


def main() -> None:
    PipubotAppFactory.from_env().run()


if __name__ == "__main__":
    main()