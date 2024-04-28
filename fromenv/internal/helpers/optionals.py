import types
import typing
from typing import Type


class OptionalTypes:
    """Utility to work with optional types."""

    @staticmethod
    def is_optional(value_type: Type) -> bool:
        """Check if type is optional."""
        origin = typing.get_origin(value_type)
        if origin is types.UnionType or origin is typing.Union:
            return types.NoneType in typing.get_args(value_type)
        return False

    @staticmethod
    def remove_optional(value_type: Type) -> Type:
        """Remove optional qualifier."""
        origin = typing.get_origin(value_type)
        if origin is typing.Optional and len(typing.get_args(value_type)) == 1:
            return typing.get_args(value_type)[0]
        else:  # Union of the form: T1 | T2 | ... | None
            actual_types = tuple(subtype for subtype in typing.get_args(value_type) if subtype is not types.NoneType)
            return typing.Union[actual_types]
