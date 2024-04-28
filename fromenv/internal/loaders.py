import abc
import dataclasses
import types
import typing
from abc import abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Type, Any, Dict, Sequence, Tuple, List

from fromenv.consts import FROM_ENV
from fromenv.errors import UnsupportedValueType, MissingRequiredVar, AmbiguousVarError
from fromenv.internal.data_classes import DataClasses
from fromenv.internal.dicts import Dicts
from fromenv.internal.tuples import Tuples


@dataclass(frozen=True)
class Config:
    """Loading configuration."""

    prefix: str | None = None
    sep: str = "_"


@dataclass
class Value:
    """Represents a value that should be loaded."""

    type: Type
    var_name: str
    qual_name: str


@dataclass
class Strategy:
    """Strategy represents a configurable logic which should be common across all loaders."""

    config: Config
    loaders: Sequence["Loader"] = dataclasses.field(default_factory=lambda: DEFAULT_LOADERS)

    def child_value(self, parent: Value, ref: Any, value_type: Type) -> Value:
        """Create child-value for the given one."""
        var_name = self.child_var_name(parent, ref)
        qual_name = self.child_qual_name(parent, ref)
        return Value(type=value_type, var_name=var_name, qual_name=qual_name)

    def resolve_loader(self, value: Value) -> "Loader":
        """Resolve loader appropriate for the given value."""
        for loader in self.loaders:
            if loader.can_load(value.type):
                return loader
        raise UnsupportedValueType(f"Unsupported value type: {value.type}")

    def root_value(self, data_class: Type) -> Value:
        """Create a root value."""
        return Value(
            type=data_class,
            var_name=self.config.prefix,
            qual_name=data_class.__name__,
        )

    def child_var_name(self, parent: Value, ref: Any) -> str:
        """Compute child-value name from parent-value and reference from parent to child."""
        this_name = str(ref).upper()
        if parent.var_name:
            return f"{parent.var_name}{self.config.sep}{this_name}"
        return this_name

    def child_qual_name(self, parent: Value, ref: Any) -> str:
        """Compute child qualified name from the given parent and value reference."""
        if DataClasses.is_dataclass(parent.type):
            return f"{parent.qual_name}.{ref}"
        return f"{parent.qual_name}[{ref}]"


@dataclass
class VarBinding:
    """Environment variables mapped to the corresponding values."""

    vars: Mapping[str, str]
    bound: Dict[str, Value] = dataclasses.field(default_factory=dict)

    def bind(self, value: Value):
        """Bind variable to the given value"""
        if value.var_name not in self.vars:
            raise MissingRequiredVar(f"Variable '{value.var_name}' not found for required value: {value.qual_name}")
        if value.var_name in self.bound:
            other = self.bound[value.var_name]
            raise AmbiguousVarError(
                f"Variable '{value.var_name}' is matched to multiple values:"
                f"\n\t1. {other.qual_name}"
                f"\n\t2. {value.qual_name}"
            )
        self.bound[value.var_name] = value


class Loader(abc.ABC):
    """Loader encapsulate type-specific loading logic."""

    @abstractmethod
    def can_load(self, value_type: Type) -> bool:
        """Check if loader can handle value type."""

    @abstractmethod
    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> Any:
        """Do load value from the environment variables."""

    @abstractmethod
    def is_present(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Check if variables representing the given value are defined."""


class BasicValueLoader(Loader):
    """Base class for basic value loaders."""

    type: Type

    def __init__(self, value_type: Type):
        self.type = value_type

    def can_load(self, value_type: Type) -> bool:
        """Check if the given value type could be handled."""
        return value_type is self.type

    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> Any:
        """Do load value."""
        env.bind(value)
        raw_value = env.vars[value.var_name]
        return self.type(raw_value)

    def is_present(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Check if value is represented by the given environment variables."""
        return value.var_name in env.vars and value.var_name not in env.bound


class BooleanLoader(BasicValueLoader):
    """Boolean value loader."""

    def __init__(self):
        super().__init__(bool)

    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Load boolean value."""
        env.bind(value)
        raw_value: str = env.vars[value.var_name]
        return raw_value.upper() == "TRUE" or raw_value == "1"


class DataClassLoader(Loader):
    """Data class loader."""

    def can_load(self, value_type: Type) -> bool:
        """Check if the requested value type is a data class."""
        return DataClasses.is_dataclass(value_type)

    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> Any:
        """Do load data class instance."""
        data_class: Type = value.type
        constructor_arguments: Dict[str, Any] = {}
        for field in dataclasses.fields(data_class):
            field_value = strategy.child_value(value, field.name, field.type)
            self._apply_metadata(field_value, field.metadata)
            field_loader = strategy.resolve_loader(field_value)
            is_present = field_loader.is_present(env, field_value, strategy)
            if DataClasses.is_required(field) and not is_present:
                raise MissingRequiredVar(
                    f"Variable is missing: {field_value.var_name} " f"(required for {field_value.qual_name})"
                )
            if is_present:
                constructor_arguments[field.name] = field_loader.load(env, field_value, strategy)
        return data_class(**constructor_arguments)

    def _apply_metadata(self, value: Value, metadata: Mapping):
        """Honor data class field metadata."""
        if FROM_ENV in metadata:
            value.var_name = str(metadata[FROM_ENV])

    def is_present(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Check if required fields are present."""
        for field in DataClasses.required_fields(value.type):
            field_value = strategy.child_value(value, field.name, field.type)
            if not Dicts.any(env.vars, query=Dicts.prefix(field_value.var_name)):
                return False
        return True


class UnionLoader(Loader):
    """Loader to handle Union-types."""

    def can_load(self, value_type: Type) -> bool:
        """Check if this is a union class."""
        origin = typing.get_origin(value_type)
        return origin is typing.Union or origin is types.UnionType

    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> Any:
        """Do load union-typed value."""
        for actual_type in typing.get_args(value.type):
            casted = dataclasses.replace(value, type=actual_type)
            loader = strategy.resolve_loader(casted)
            if loader.is_present(env, casted, strategy):
                return loader.load(env, casted, strategy)
        raise MissingRequiredVar(
            f"Failed to load {value.qual_name} because none of the {value.type} types are present."
        )

    def is_present(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Check if some of the united types could be loaded."""
        for actual_type in typing.get_args(value.type):
            casted = dataclasses.replace(value, type=actual_type)
            loader = strategy.resolve_loader(casted)
            if loader.is_present(env, casted, strategy):
                return True
        return False


class ListLoader(Loader):
    """List loader."""

    def can_load(self, value_type: Type) -> bool:
        """Check if the value type is list."""
        origin = typing.get_origin(value_type)
        return value_type == list or origin is list or origin is List or origin is typing.Sequence

    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> List:
        """Do load list value."""
        items: List = []
        item_type: Type = self._item_type(value)
        current_index: int = 0
        current_item: Value = strategy.child_value(value, current_index, item_type)
        item_loader: Loader = strategy.resolve_loader(current_item)
        while item_loader.is_present(env, current_item, strategy):
            loaded_item = item_loader.load(env, current_item, strategy)
            items.append(loaded_item)
            current_index += 1
            current_item = strategy.child_value(value, current_index, item_type)
        return items

    @staticmethod
    def _item_type(value: Value) -> Type:
        """Get item type."""
        type_args: Tuple[Type, ...] = typing.get_args(value.type)
        if not type_args:
            raise UnsupportedValueType(f"Cannot load untyped list: {value.qual_name}:{value.type}")
        return type_args[0]

    def is_present(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Check if list is present."""
        return True  # List may be empty in which case it is also present.


class TupleLoader(Loader):
    """Tuple loader."""

    def can_load(self, value_type: Type) -> bool:
        """Check if value type is tuple."""
        origin = typing.get_origin(value_type)
        return value_type == tuple or origin is tuple or origin is typing.Tuple

    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> Any:
        """Do load the tuple."""
        if Tuples.is_variable(value.type):
            return self._load_variable_tuple(env, value, strategy)
        elif Tuples.is_fixed(value.type):
            return self._load_fixed_tuple(env, value, strategy)
        elif Tuples.is_untyped(value.type):
            raise UnsupportedValueType(f"Cannot load untyped tuple: {value.qual_name}:{value.type}")
        raise ValueError(f"Not a tuple type: {value.type}")

    @staticmethod
    def _load_variable_tuple(env: VarBinding, value: Value, strategy: Strategy) -> Any:
        """Load tuple of any length."""
        item_type = Tuples.item_type(value.type)
        current_index: int = 0
        current_item: Value = strategy.child_value(value, current_index, item_type)
        item_loader: Loader = strategy.resolve_loader(current_item)
        items: List[Any] = []
        while item_loader.is_present(env, current_item, strategy):
            item_value = item_loader.load(env, current_item, strategy)
            items.append(item_value)
            current_index += 1
            current_item: Value = strategy.child_value(value, current_index, item_type)
        return tuple(items)

    @staticmethod
    def _load_fixed_tuple(env: VarBinding, value: Value, strategy: Strategy) -> Any:
        """Load tuple of any length."""
        items: List[Any] = []
        item_types = typing.get_args(value.type)
        for index, item_type in enumerate(item_types):
            item = strategy.child_value(value, index, item_type)
            item_loader = strategy.resolve_loader(item)
            items.append(item_loader.load(env, item, strategy))
        return tuple(items)

    def is_present(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Check if tuple is present."""
        return True  # Tuple may be empty in which case it is also present


DEFAULT_LOADERS: Tuple[Loader, ...] = (
    BasicValueLoader(int),
    BasicValueLoader(float),
    BasicValueLoader(str),
    BooleanLoader(),
    DataClassLoader(),
    UnionLoader(),
    ListLoader(),
    TupleLoader(),
)
