"""
The from_env(DataClass) API works by inspecting data types.
Some data types may produce values without consuming any
environment variables. Such values are called "type-specific
defaults" and denoted as "default(T)" for type T throughout
library documentation. Also, data class fields may have default
values. Those are called "field-specific defaults" and denoted
as "default(field)".

In some situations multiple different values of the same type
may be produced without consuming any environment variables.
The following convention is used to unambiguously determine
which default value should be produced:
1. If there is a field F of the type T, and default(F) is defined,
    then default(F) should be used instead of default(T)
2. default(Optional[T]) is always None
3. default(List[T]) is always empty list []
4. default(Tuple[T, ...]) is always empty tuple ()
5. default(Tuple[T1, ..., Tn]) is a tuple of defaults
   (default(T1), ..., default(Tn))

This test-module checks if the above convention is correctly
implemented.
"""

from dataclasses import dataclass, field
from typing import List, Tuple

from fromenv import from_env


def test_type_specific_default_for_fields():
    """Check default value for each data type."""

    @dataclass
    class Nested:
        """Class without required fields."""

        value: int = 0

    @dataclass
    class TestData:
        """No field-specific defaults."""

        nested: Nested
        list: List[str]
        tuple: Tuple[str, ...]
        fixed_tuple: Tuple[Nested, Nested]
        optional: str | None

    assert from_env(TestData, {}) == TestData(
        nested=Nested(),
        list=[],
        tuple=(),
        fixed_tuple=(Nested(), Nested()),
        optional=None,
    )


def test_field_specific_default_instead_of_type_specific():
    """Check that field-specific defaults overrides type-specific ones."""

    @dataclass(frozen=True)
    class Nested:
        """Class without required fields."""

        value: str = "type-specific"

    @dataclass
    class TestData:
        """No field-specific defaults."""

        nested: Nested = Nested("field-specific")
        list: List[str] = field(default_factory=lambda: ["field-specific"])
        tuple: Tuple[str, ...] = ("field-specific",)
        fixed_tuple: Tuple[Nested, Nested] = (Nested("field"), Nested("specific"))
        optional: str | None = "field-specific"

    assert from_env(TestData, {}) == TestData(
        nested=Nested("field-specific"),
        list=["field-specific"],
        tuple=("field-specific",),
        fixed_tuple=(Nested("field"), Nested("specific")),
        optional="field-specific",
    )
