class MissingRequiredVar(Exception):
    """Represents missing required variable."""


class AmbiguousVarError(Exception):
    """Indicates an ambiguous key -> field matching."""


class UnsupportedValueType(Exception):
    """Indicates value type is not supported."""
