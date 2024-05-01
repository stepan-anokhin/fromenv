import dataclasses
import json
from dataclasses import dataclass
from typing import Union, List, Tuple, Optional

import pytest

from fromenv import from_env, MissingRequiredVar
from fromenv.model import Metadata


def test_basic():
    @dataclass
    class TestData:
        int_value: int
        bool_value: bool
        str_value: str
        float_value: float

    env = {
        "INT_VALUE": "42",
        "BOOL_VALUE": "true",
        "STR_VALUE": "anything",
        "FLOAT_VALUE": "42.0",
    }

    values = from_env(TestData, env=env)

    assert values.int_value == int(env["INT_VALUE"])
    assert values.str_value == env["STR_VALUE"]
    assert values.float_value == float(env["FLOAT_VALUE"])
    assert values.bool_value == (env["BOOL_VALUE"].upper() == "TRUE")


def test_bool():
    @dataclass
    class TestData:
        bool_value: bool

    assert from_env(TestData, {"BOOL_VALUE": "TRUE"}).bool_value is True
    assert from_env(TestData, {"BOOL_VALUE": "true"}).bool_value is True
    assert from_env(TestData, {"BOOL_VALUE": "TrUe"}).bool_value is True
    assert from_env(TestData, {"BOOL_VALUE": "1"}).bool_value is True
    assert from_env(TestData, {"BOOL_VALUE": "yes"}).bool_value is True
    assert from_env(TestData, {"BOOL_VALUE": "FALSE"}).bool_value is False
    assert from_env(TestData, {"BOOL_VALUE": "faLSe"}).bool_value is False
    assert from_env(TestData, {"BOOL_VALUE": "0"}).bool_value is False
    assert from_env(TestData, {"BOOL_VALUE": "no"}).bool_value is False
    with pytest.raises(ValueError):
        from_env(TestData, {"BOOL_VALUE": "invalid"})


def test_metadata():
    @dataclass
    class TestData:
        some_field: str = dataclasses.field(metadata={"fromenv": "VAR_FROM_METADATA"})

    assert from_env(TestData, {"VAR_FROM_METADATA": "expected"}).some_field == "expected"


def test_default():
    @dataclass
    class TestData:
        optional: str = "default"

    assert from_env(TestData, {}).optional == "default"
    assert from_env(TestData, {"OPTIONAL": "specified"}).optional == "specified"


def test_union():
    @dataclass
    class TestData:
        or_type_field: str | int
        union_field: Union[int, str]

    data = from_env(TestData, {"OR_TYPE_FIELD": "10", "UNION_FIELD": "10"})
    assert data.or_type_field == "10"
    assert data.union_field == 10


def test_list():
    @dataclass
    class ItemType:
        required: int
        optional: str = "default"

    @dataclass
    class TestData:
        nested_list: List[ItemType]
        basic_list: list[int]

    assert from_env(TestData, {}) == TestData([], [])
    assert from_env(
        TestData,
        {
            "NESTED_LIST_0_REQUIRED": "0",
            "NESTED_LIST_1_REQUIRED": "1",
            "NESTED_LIST_1_OPTIONAL": "specified",
        },
    ).nested_list == [ItemType(0), ItemType(1, "specified")]

    assert from_env(TestData, {"BASIC_LIST_0": "100", "BASIC_LIST_1": "200"}).basic_list == [100, 200]


def test_var_tuple():
    @dataclass
    class ItemType:
        required: int
        optional: str = "default"

    @dataclass
    class TestData:
        nested_tuple: Tuple[ItemType, ...]
        basic_tuple: tuple[int, ...]

    assert from_env(TestData, {}) == TestData((), ())
    assert from_env(
        TestData,
        {
            "NESTED_TUPLE_0_REQUIRED": "0",
            "NESTED_TUPLE_1_REQUIRED": "1",
            "NESTED_TUPLE_1_OPTIONAL": "specified",
        },
    ).nested_tuple == (ItemType(0), ItemType(1, "specified"))

    assert from_env(TestData, {"BASIC_TUPLE_0": "100", "BASIC_TUPLE_1": "200"}).basic_tuple == (100, 200)


def test_fixed_tuple():
    @dataclass
    class TestData:
        first: Tuple[int, str, bool]
        second: tuple[int, str, bool]

    assert from_env(
        TestData,
        {
            "FIRST_0": "100",
            "FIRST_1": "first-str",
            "FIRST_2": "false",
            "SECOND_0": "200",
            "SECOND_1": "second-str",
            "SECOND_2": "true",
        },
    ) == TestData((100, "first-str", False), (200, "second-str", True))


def test_incomplete_fixed_tuple_with_default():

    default = (0, "", False)

    @dataclass
    class TestData:
        field: tuple[int, str, bool] = default

    assert from_env(TestData, {"FIELD_0": "100", "FIELD_1": "specified"}).field == default


def test_incomplete_fixed_tuple_without_default():

    @dataclass
    class TestData:
        field: tuple[int, str, bool]

    with pytest.raises(MissingRequiredVar):
        from_env(TestData, {"FIELD_0": "100", "FIELD_1": "specified"})


def test_nested_tuples():
    @dataclass
    class TestData:
        tuple: Tuple[int, str, Tuple[int, str, Tuple[str, ...]]]

    assert from_env(
        TestData,
        {
            "TUPLE_0": "0",
            "TUPLE_1": "str-outer",
            "TUPLE_2_0": "1",
            "TUPLE_2_1": "str-nested",
            "TUPLE_2_2_0": "str-deepest-1",
            "TUPLE_2_2_1": "str-deepest-2",
        },
    ).tuple == (0, "str-outer", (1, "str-nested", ("str-deepest-1", "str-deepest-2")))


def test_optional():
    @dataclass
    class Nested:
        optional: Optional[int]

    @dataclass
    class TestData:
        nested: Nested | None
        union_basic: str | None
        optional_basic: Optional[str]

    assert from_env(TestData, {}) == TestData(None, None, None)
    assert from_env(TestData, {"NESTED_OPTIONAL": "42"}) == TestData(Nested(42), None, None)
    assert from_env(TestData, {"UNION_BASIC": "specified"}) == TestData(None, "specified", None)
    assert from_env(TestData, {"OPTIONAL_BASIC": "specified"}) == TestData(None, None, "specified")


def test_metadata_name():
    @dataclass
    class TestData:
        first_field: int = dataclasses.field(metadata={"fromenv": "FIRST"})
        second_field: bool = dataclasses.field(metadata={"fromenv": Metadata(name="SECOND")})

    assert from_env(TestData, {"FIRST": "42", "SECOND": "true"}) == TestData(42, True)


def test_custom_loader():
    @dataclass
    class TestData:
        field_name: List[int] = dataclasses.field(metadata={"fromenv": Metadata(load=json.loads)})

    assert from_env(TestData, {"FIELD_NAME": "[1, 2, 3]"}) == TestData([1, 2, 3])


def test_optional_fixed_tuple_item():
    @dataclass
    class TestData:
        tuple: tuple[int | None, str | None, bool | None] | None

    assert from_env(TestData, {}).tuple is None
    assert from_env(TestData, {"TUPLE_0": "42"}).tuple == (42, None, None)
    assert from_env(TestData, {"TUPLE_1": "specified"}).tuple == (None, "specified", None)
    assert from_env(TestData, {"TUPLE_2": "true"}).tuple == (None, None, True)


def test_optional_nested():
    @dataclass
    class Nested:
        attr: str | None

    @dataclass
    class TestData:
        nested: Nested | None

    assert from_env(TestData, {}).nested is None
    assert from_env(TestData, {"NESTED_ATTR": "specified"}).nested.attr == "specified"


def test_optional_list_items():

    @dataclass
    class Item:
        attr: str | None

    @dataclass
    class TestData:
        list: List[Item | None]

    assert from_env(TestData, {}).list == []
    assert from_env(TestData, {"LIST_1_ATTR": "specified"}).list == []
    assert from_env(TestData, {"LIST_0_ATTR": "specified"}).list == [Item("specified")]


def test_optional_list_of_optional_items():

    @dataclass
    class Item:
        attr: str | None

    @dataclass
    class TestData:
        list: List[Item | None] | None

    assert from_env(TestData, {}).list is None
    assert from_env(TestData, {"LIST_1_ATTR": "specified"}).list is None
    assert from_env(TestData, {"LIST_0_ATTR": "specified"}).list == [Item("specified")]


def test_optional_default_tuple():

    @dataclass
    class Item:
        attr: str | None

    default: tuple[Item | None, Item | None] = (Item("default-0"), Item("default-1"))

    @dataclass
    class TestData:
        tuple_value: tuple[Item | None, Item | None] | None = default

    assert from_env(TestData, {}).tuple_value == default


def test_optional_field_with_default_value():
    @dataclass
    class Nested:
        optional: str | None

    default = Nested("default")

    @dataclass
    class TestData:
        nested: Nested | None = default
        optional: str | None = "default"

    assert from_env(TestData, {}) == TestData(default, "default")


def test_default_tuple():
    @dataclass
    class TestData:
        nullable_tuple_required_items: tuple[int, int] | None
        nullable_items: tuple[int | None, int | None]
        nullable_tuple: tuple[int | None, int | None] | None
        nullable_default: tuple[int | None, int | None] | None = (1, 2)

    assert from_env(TestData, {}) == TestData(
        nullable_tuple_required_items=None, nullable_items=(None, None), nullable_tuple=None, nullable_default=(1, 2)
    )
