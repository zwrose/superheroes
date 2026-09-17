"""Closed vocabulary for ``<field>Source`` markers on ``resolvedInputs`` snapshots (#1296).

Each marker names how a resolved field's value was chosen. This module is the one home for that
vocabulary — add a member here first and nowhere else.
"""

CALLER = "caller"
DEFAULT = "default"
CLAMPED = "clamped"
RESOLVED = "resolved"
DECLARED_NONE = "declared-none"
SEAT = "seat"
SEAT_DEFAULT = "seat-default"
LEGACY_JOURNAL = "legacy-journal"
RUN_DIR_POINTER = "run-dir-pointer"
ENVIRONMENT_VARIABLE = "environment-variable"
TEMP_DIRECTORY = "temp-directory"

SOURCE_MARKERS = frozenset({
    CALLER,
    DEFAULT,
    CLAMPED,
    RESOLVED,
    DECLARED_NONE,
    SEAT,
    SEAT_DEFAULT,
    LEGACY_JOURNAL,
    RUN_DIR_POINTER,
    ENVIRONMENT_VARIABLE,
    TEMP_DIRECTORY,
})


class UndeclaredSourceMarker(ValueError):
    """Raised when a producer attempts to write an undeclared ``<field>Source`` marker."""
