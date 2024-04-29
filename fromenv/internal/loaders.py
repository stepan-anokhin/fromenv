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
from fromenv.internal.helpers.data_classes import DataClasses
from fromenv.internal.helpers.dicts import Dicts
from fromenv.internal.helpers.optionals import OptionalTypes
from fromenv.internal.helpers.tuples import Tuples
from fromenv.model import Metadata


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
    metadata: Metadata | None = None


@dataclass
class Strategy:
    """Strategy represents a configurable logic which should be common across all loaders."""

    config: Config
    loaders: Sequence["Loader"] = dataclasses.field(default_factory=lambda: DEFAULT_LOADERS)

    def child_value(self, parent: Value, ref: Any, value_type: Type, metadata: Metadata | None = None) -> Value:
        """Create child-value for the given one."""
        var_name = self.child_var_name(parent, ref)
        qual_name = self.child_qual_name(parent, ref)
        if metadata is not None and metadata.name is not None:
            var_name = metadata.name
        return Value(type=value_type, var_name=var_name, qual_name=qual_name, metadata=metadata)

    def resolve_loader(self, value: Value) -> "Loader":
        """Resolve loader appropriate for the given value."""
        for loader in self.loaders:
            if loader.can_load(value):
                return loader
        raise UnsupportedValueType(f"Unsupported type: {value.type} of a field {value.qual_name}")

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
    def can_load(self, value: Value) -> bool:
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

    def can_load(self, value: Value) -> bool:
        """Check if the given value type could be handled."""
        return value.type is self.type

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

    def can_load(self, value: Value) -> bool:
        """Check if the requested value type is a data class."""
        return DataClasses.is_dataclass(value.type)

    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> Any:
        """Do load data class instance."""
        data_class: Type = value.type
        constructor_arguments: Dict[str, Any] = {}
        for field in dataclasses.fields(data_class):
            metadata: Metadata = self._resolve_metadata(value, field)
            field_value = strategy.child_value(value, field.name, field.type, metadata)
            field_loader = strategy.resolve_loader(field_value)
            is_present = field_loader.is_present(env, field_value, strategy)
            is_optional = OptionalTypes.is_optional(field_value.type)
            if DataClasses.is_required(field) and not is_optional and not is_present:
                raise MissingRequiredVar(
                    f"Variable is missing: {field_value.var_name} " f"(required for {field_value.qual_name})"
                )
            if DataClasses.is_required(field) and is_optional and not is_present:
                constructor_arguments[field.name] = None
            if is_present:
                constructor_arguments[field.name] = field_loader.load(env, field_value, strategy)
        return data_class(**constructor_arguments)

    @staticmethod
    def _resolve_metadata(data: Value, field: dataclasses.Field) -> Metadata | None:
        """Resolve value metadata."""
        if FROM_ENV not in field.metadata:
            return None
        metadata = field.metadata[FROM_ENV]
        if metadata is None:
            return None
        elif isinstance(metadata, str):
            return Metadata(name=metadata)
        elif isinstance(metadata, Metadata):
            return metadata
        raise TypeError(f"Unexpected type for field metadata: {data.qual_name}.{field.name}: {type(metadata)}")

    def is_present(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Check if required fields are present."""
        for field in DataClasses.required_fields(value.type):
            field_value = strategy.child_value(value, field.name, field.type)
            if not Dicts.any(env.vars, query=Dicts.prefix(field_value.var_name)):
                return False
        return True


class UnionLoader(Loader):
    """Loader to handle Union-types."""

    def can_load(self, value: Value) -> bool:
        """Check if this is a union class."""
        origin = typing.get_origin(value.type)
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

    def can_load(self, value: Value) -> bool:
        """Check if the value type is list."""
        origin = typing.get_origin(value.type)
        return value == list or origin is list or origin is List or origin is typing.Sequence

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

    def can_load(self, value: Value) -> bool:
        """Check if value type is tuple."""
        origin = typing.get_origin(value.type)
        return value == tuple or origin is tuple or origin is typing.Tuple

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


class OptionalLoader(Loader):
    """Optional type loader."""

    def can_load(self, value: Value) -> bool:
        """Check if type is optional."""
        return OptionalTypes.is_optional(value.type)

    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> Any:
        """Load optional value."""
        actual_type = OptionalTypes.remove_optional(value.type)
        actual_value = dataclasses.replace(value, type=actual_type)
        loader = strategy.resolve_loader(actual_value)
        if loader.is_present(env, actual_value, strategy):
            return loader.load(env, actual_value, strategy)
        return None

    def is_present(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Check if value is present."""
        actual_type = OptionalTypes.remove_optional(value.type)
        actual_value = dataclasses.replace(value, type=actual_type)
        loader = strategy.resolve_loader(actual_value)
        return loader.is_present(env, actual_value, strategy)


class CustomLoader(Loader):
    """Loader that uses the `load` function from metadata to parse the value."""

    def can_load(self, value: Value) -> bool:
        """Check if custom loader is defined."""
        return value.metadata is not None and value.metadata.load is not None

    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> Any:
        """Do load the value with a custom loader."""
        env.bind(value)
        return value.metadata.load(env.vars[value.var_name])

    def is_present(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Check if the corresponding variable is defined."""
        return value.var_name in env.vars


DEFAULT_LOADERS: Tuple[Loader, ...] = (
    CustomLoader(),
    OptionalLoader(),
    BasicValueLoader(int),
    BasicValueLoader(float),
    BasicValueLoader(str),
    BooleanLoader(),
    DataClassLoader(),
    UnionLoader(),
    ListLoader(),
    TupleLoader(),
)
