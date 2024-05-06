from dataclasses import dataclass
from typing import Tuple

from fromenv import from_env


def test_basic_item_type():
    @dataclass
    class TestData:
        tuple: tuple[int, ...]

    assert from_env(TestData, {"TUPLE_0": "1", "TUPLE_1": "2"}).tuple == (1, 2)
    assert from_env(TestData, {}).tuple == ()


def test_optional_tuple():
    @dataclass
    class TestData:
        tuple: Tuple[int, ...] | None

    assert from_env(TestData, {"TUPLE_0": "1", "TUPLE_1": "2"}).tuple == (1, 2)
    assert from_env(TestData, {}).tuple is None


def test_tuple_of_objects():
    @dataclass
    class Item:
        value: int | None

    @dataclass
    class TestData:
        tuple: Tuple[Item, ...]

    assert from_env(TestData, {}).tuple == ()
    assert from_env(TestData, {"TUPLE_0_VALUE": "1", "TUPLE_1_VALUE": "2"}).tuple == (Item(1), Item(2))


def test_specified_length():
    @dataclass
    class Item:
        value: int | None

    @dataclass
    class TestData:
        tuple: Tuple[Item, ...]
        tuple_of_optional: Tuple[Item | None, ...]

    assert from_env(TestData, {}) == TestData((), ())

    # Empty tuples
    assert from_env(TestData, {"TUPLE_LEN": "0", "TUPLE_OF_OPTIONAL": "0"}) == TestData((), ())

    # All defaults
    assert from_env(
        TestData,
        {
            "TUPLE_LEN": "2",
            "TUPLE_OF_OPTIONAL_LEN": "2",
        },
    ) == TestData(
        (Item(None), Item(None)),
        (None, None),
    )

    # Non-defaults, defaults and extras
    assert from_env(
        TestData,
        {
            "TUPLE_LEN": "2",
            "TUPLE_1_VALUE": "1",
            "TUPLE_2_VALUE": "2",
            "TUPLE_OF_OPTIONAL_LEN": "2",
            "TUPLE_OF_OPTIONAL_1_VALUE": "1",
            "TUPLE_OF_OPTIONAL_2_VALUE": "2",
        },
    ) == TestData(
        (Item(None), Item(1)),
        (None, Item(1)),
    )
