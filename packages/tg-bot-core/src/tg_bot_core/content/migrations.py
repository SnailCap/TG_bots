from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping

from .models import CONTENT_SCHEMA_VERSION


class ContentMigrationError(ValueError):
    pass


def migrate_content_document(
    value: Mapping[str, Any], *, target_version: int = CONTENT_SCHEMA_VERSION
) -> dict[str, Any]:
    """Return a detached document at the requested content-schema version.

    Version 1 is the first persisted BotContentDocument format. Keeping the
    migration boundary explicit makes future v1 -> v2 migrations sequential
    without coupling them to the project schema version.
    """

    migrated = deepcopy(dict(value))
    version = migrated.get("schemaVersion")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ContentMigrationError("Content document schemaVersion must be an integer.")
    if version > target_version:
        raise ContentMigrationError(
            f"Content document schemaVersion {version} is newer than supported version {target_version}."
        )
    if version < 1:
        raise ContentMigrationError(
            f"Content document schemaVersion {version} has no supported migration path."
        )

    migrations: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}
    while version < target_version:
        migration = migrations.get(version)
        if migration is None:
            raise ContentMigrationError(
                f"No content document migration exists from schemaVersion {version}."
            )
        migrated = migration(migrated)
        version += 1
        migrated["schemaVersion"] = version
    return migrated
