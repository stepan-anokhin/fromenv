"""
In some cases multiple values V1, ..., Vn of type T could be produced
with footprint(V1) = ... = footprint(Vn) = empty set. Such values
are called "defaults". By convention, only one of those values could
be produced. How do we achieve completeness in such situation?

Solution:

For each possible default value there should be a way to produce
this default by consuming at least one variable.

We define the following ways to do that for each type:
1. For lists and tuples of any length we may explicitly specify
   length = 0 to get empty list or empty tuple correspondingly.
   If "VAR_NAME_<index>" variables are expected to represent
   list or tuple items, then we may set "VAR_NAME_LEN=0" to
   specify empty array or tuple.
2. For Optional[T] to produce None we define "IS_NONE__" attribute:
   if "VAR_NAME" variable represents Optional[T] value, then
   "VAR_NAME_IS_NONE__" variable indicates that None should be produced.
3. For data class with all fields having default values simply explicitly
   specify default value for any field.

This module verifies that the above approach works correctly.
"""

from dataclasses import dataclass, field
from typing import List, Tuple

from fromenv import from_env


def test_empty_list_instead_of_none():
    @dataclass
    class TestData:
        list: List[int] | None

    assert from_env(TestData, {}).list is None
    assert from_env(TestData, {"LIST_LEN": "0"}).list == []


def test_empty_tuple_instead_of_none():
    @dataclass
    class TestData:
        tuple: Tuple[int, ...] | None

    assert from_env(TestData, {}).tuple is None
    assert from_env(TestData, {"TUPLE_LEN": "0"}).tuple == ()


def test_empty_string_instead_of_none():
    @dataclass
    class TestData:
        string: str | None

    assert from_env(TestData, {}).string is None
    assert from_env(TestData, {"STRING": ""}).string == ""


def test_default_data_class_instead_of_none():

    @dataclass
    class Nested:
        value: str = "default"
        other: str = "other-default"

    @dataclass
    class TestData:
        nested: Nested | None

    assert from_env(TestData, {}).nested is None
    assert from_env(TestData, {"NESTED_VALUE": "default"}).nested == Nested()


def test_empty_list_instead_of_field_default():
    @dataclass
    class TestData:
        list: List[str] = field(default_factory=lambda: ["field", "default"])

    assert from_env(TestData, {}).list == ["field", "default"]
    assert from_env(TestData, {"LIST_LEN": "0"}).list == []


def test_empty_tuple_instead_of_field_default():
    @dataclass
    class TestData:
        tuple: Tuple[str, ...] = ("field", "default")

    assert from_env(TestData, {}).tuple == ("field", "default")
    assert from_env(TestData, {"TUPLE_LEN": "0"}).tuple == ()


def test_empty_string_instead_of_field_default():
    @dataclass
    class TestData:
        string: str = "default"

    assert from_env(TestData, {}).string == "default"
    assert from_env(TestData, {"STRING": ""}).string == ""


def test_data_class_default_instead_of_field_default():

    @dataclass
    class Nested:
        value: str = "nested-default"

    @dataclass
    class TestData:
        nested: Nested = Nested("field-default")

    assert from_env(TestData, {}).nested == Nested("field-default")
    assert from_env(TestData, {"NESTED_VALUE": "nested-default"}).nested == Nested()


def test_none_instead_of_field_default():

    @dataclass
    class Nested:
        value: str = "nested-default"

    @dataclass
    class TestData:
        list: List[str] | None = field(default_factory=lambda: ["field", "default"])
        string: str | None = "field-default"
        tuple: Tuple[str, ...] | None = ("field", "default")
        nested: Nested | None = Nested("field-default")

    assert from_env(TestData, {}) == TestData()
    assert from_env(
        TestData,
        {
            "LIST_IS_NONE__": "",
            "STRING_IS_NONE__": "",
            "TUPLE_IS_NONE__": "",
            "NESTED_IS_NONE__": "",
        },
    ) == TestData(list=None, string=None, tuple=None, nested=None)


def test_type_default_instead_of_field_default_and_none():

    @dataclass
    class Nested:
        value: str = "nested-default"

    @dataclass
    class TestData:
        list: List[str] | None = field(default_factory=lambda: ["field", "default"])
        string: str | None = "field-default"
        tuple: Tuple[str, ...] | None = ("field", "default")
        nested: Nested | None = Nested("field-default")

    assert from_env(TestData, {}) == TestData()
    assert from_env(
        TestData,
        {
            "LIST_LEN": "0",
            "STRING": "",
            "TUPLE_LEN": "0",
            "NESTED_VALUE": "nested-default",
        },
    ) == TestData(list=[], string="", tuple=(), nested=Nested())
