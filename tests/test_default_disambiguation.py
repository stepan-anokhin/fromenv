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
