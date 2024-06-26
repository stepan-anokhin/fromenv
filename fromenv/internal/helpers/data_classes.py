"""Collection of utils to work with dataclasses."""

import dataclasses
import inspect
from typing import Type, Iterable


class DataClasses:
    """DataClasses provides static utility methods
    to work data classes."""

    @staticmethod
    def is_dataclass(data_class: Type) -> bool:
        """Check if the argument is a data class object."""
        return inspect.isclass(data_class) and dataclasses.is_dataclass(data_class)

    @staticmethod
    def has_default(field: dataclasses.Field) -> bool:
        """Check if the field has a default value."""
        return not (field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING)

    @staticmethod
    def required_fields(data_class: Type) -> Iterable[dataclasses.Field]:
        """Iterate over required fields."""
        return (field for field in dataclasses.fields(data_class) if not DataClasses.has_default(field))

    @staticmethod
    def default_value(field: dataclasses.Field):
        """Get default value."""
        if field.default is not dataclasses.MISSING:
            return field.default
        if field.default_factory is not dataclasses.MISSING:
            return field.default_factory()
        raise ValueError(f"Field {field} doesn't have default value.")
