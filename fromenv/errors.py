from typing import Type


class LoadingError(Exception):
    """Parent class for all loading errors."""


class MissingRequiredVar(LoadingError):
    """Indicates that some required environment variable is not defined."""

    var_name: str
    qual_value: str

    def __init__(self, var_name: str, qual_name: str, message: str | None = None):
        super().__init__(message or f"Variable '{var_name}' not found (required for {qual_name})")
        self.var_name = var_name
        self.qual_value = qual_name


class AmbiguousVarError(LoadingError):
    """Indicates ambiguous environment variable binding to basic values."""

    var_name: str
    first_qual_name: str
    second_qual_name: str

    def __init__(self, var_name: str, first_qual_name: str, second_qual_name: str, message: str | None = None):
        super().__init__(
            message or f"Variable '{var_name}' has ambiguous binding:\n\t1. {first_qual_name}\n\t2. {second_qual_name}"
        )
        self.var_name = var_name
        self.first_qual_name = first_qual_name
        self.second_qual_name = second_qual_name


class UnsupportedValueType(LoadingError):
    """Indicates value type is not supported."""

    qual_name: str
    value_type: Type

    def __init__(self, qual_name: str, value_type: Type, message: str | None = None):
        super().__init__(message or f"{qual_name} has unsupported type: {value_type}")
        self.qual_name = qual_name
        self.value_type = value_type


class UnionLoadingError(LoadingError):
    """Indicates that none of the union alternatives was successfully loaded."""

    qual_name: str
    value_type: Type

    def __init__(self, qual_name: str, value_type: Type, message: str | None = None):
        super().__init__(message or f"None of the union type alternatives could be loaded for {qual_name}")
        self.qual_name = qual_name
        self.value_type = value_type
