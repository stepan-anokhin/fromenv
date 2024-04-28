import typing
from typing import Type, Tuple


class Tuples:
    """Utilities to work with tuples."""

    @staticmethod
    def is_tuple(value_type: Type) -> bool:
        """Check if value type is a tuple."""
        origin: Type = typing.get_origin(value_type)
        return value_type is tuple or origin is tuple or origin is Tuple

    @staticmethod
    def is_untyped(value_type: Type) -> bool:
        """Check if type is a fixed-length tuple."""
        return Tuples.is_tuple(value_type) and len(typing.get_args(value_type)) == 0

    @staticmethod
    def is_fixed(value_type: Type) -> bool:
        """Check if type is a fixed-length tuple."""
        return Tuples.is_tuple(value_type) and not Tuples.is_variable(value_type) and not Tuples.is_untyped(value_type)

    @staticmethod
    def is_variable(value_type: Type) -> bool:
        """Check if type is any-length tuple."""
        if not Tuples.is_tuple(value_type):
            return False
        item_types: Tuple[Type, ...] = typing.get_args(value_type)
        if len(item_types) != 2:
            return False
        return item_types[1] is Ellipsis

    @staticmethod
    def item_type(value_type: Type) -> Type:
        """Get item type is a var-length tuple type."""
        if not Tuples.is_variable(value_type):
            raise ValueError(f"Not a variable-length tuple type: {value_type}")
        return typing.get_args(value_type)[0]
