from typing import Type


class Types:
    """Utilities to work with any types."""

    @staticmethod
    def name(value_type: Type) -> str:
        """Get more human-readable representation of the type."""
        if hasattr(value_type, "__name__"):
            return value_type.__name__
        return repr(value_type)
