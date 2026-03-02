from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class UiBindingsManifest:
    """
    Central place to declare which packages/modules must be imported
    to register UI bindings (side effect imports).
    """

    packages: Sequence[str]


PIPUBOT_UI_BINDINGS = UiBindingsManifest(
    packages=(
        # Put your "root" package(s) that contain binding registrations.
        # If it's a package, UiBindingsPlugin will walk and import submodules recursively.
        "pipubot.ui.components",
    )
)