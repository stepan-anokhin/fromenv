from dataclasses import dataclass
from typing import List

from fromenv import from_env


def test_basic_item_type():
    @dataclass
    class TestData:
        list: List[int]

    assert from_env(TestData, {"LIST_0": "1", "LIST_1": "2"}).list == [1, 2]
    assert from_env(TestData, {}).list == []


def test_optional_list():
    @dataclass
    class TestData:
        list: list[int] | None

    assert from_env(TestData, {"LIST_0": "1", "LIST_1": "2"}).list == [1, 2]
    assert from_env(TestData, {}).list is None


def test_list_of_objects():
    @dataclass
    class Item:
        value: int | None

    @dataclass
    class TestData:
        list: list[Item]

    assert from_env(TestData, {}).list == []
    assert from_env(TestData, {"LIST_0_VALUE": "1", "LIST_1_VALUE": "2"}).list == [Item(1), Item(2)]


def test_specified_length():
    @dataclass
    class Item:
        value: int | None

    @dataclass
    class TestData:
        list: List[Item]
        list_of_optional: List[Item | None]

    assert from_env(TestData, {}) == TestData([], [])

    # Empty lists
    assert from_env(TestData, {"LIST_LEN": "0", "LIST_OF_OPTIONAL": "0"}) == TestData([], [])

    # All defaults
    assert from_env(
        TestData,
        {
            "LIST_LEN": "2",
            "LIST_OF_OPTIONAL_LEN": "2",
        },
    ) == TestData(
        [Item(None), Item(None)],
        [None, None],
    )

    # Non-defaults, defaults and extras
    assert from_env(
        TestData,
        {
            "LIST_LEN": "2",
            "LIST_1_VALUE": "1",
            "LIST_2_VALUE": "2",
            "LIST_OF_OPTIONAL_LEN": "2",
            "LIST_OF_OPTIONAL_1_VALUE": "1",
            "LIST_OF_OPTIONAL_2_VALUE": "2",
        },
    ) == TestData(
        [Item(None), Item(1)],
        [None, Item(1)],
    )
