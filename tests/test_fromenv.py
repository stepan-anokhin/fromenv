import dataclasses
from dataclasses import dataclass
from typing import Union

from fromenv import from_env


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
    assert from_env(TestData, {"BOOL_VALUE": "FALSE"}).bool_value is False
    assert from_env(TestData, {"BOOL_VALUE": "faLSe"}).bool_value is False
    assert from_env(TestData, {"BOOL_VALUE": "0"}).bool_value is False
    assert from_env(TestData, {"BOOL_VALUE": "whatever"}).bool_value is False


def test_metadata():
    @dataclass
    class TestData:
        some_field: str = dataclasses.field(metadata={"fromenv": "VAR_FROM_METADATA"})

    assert from_env(TestData, {"VAR_FROM_METADATA": "expected"}).some_field == "expected"


def test_default():
    @dataclass
    class TestData:
        optional: str = "default-value"

    assert from_env(TestData, {}).optional == "default-value"
    assert from_env(TestData, {"OPTIONAL": "specified-value"}).optional == "specified-value"


def test_union():
    @dataclass
    class TestData:
        or_type_field: str | int
        union_field: Union[int, str]

    data = from_env(TestData, {"OR_TYPE_FIELD": "10", "UNION_FIELD": "10"})
    assert data.or_type_field == "10"
    assert data.union_field == 10
