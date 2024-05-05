import abc
import dataclasses
import types
import typing
from abc import abstractmethod
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from types import UnionType
from typing import Type, Any, Dict, Sequence, Tuple, List, Iterator

from fromenv.consts import FROM_ENV
from fromenv.errors import (
    UnsupportedValueType,
    MissingRequiredVar,
    AmbiguousVarError,
    UnionLoadingError,
    InvalidVariableFormat,
)
from fromenv.internal.helpers.data_classes import DataClasses
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

    def child_value(
        self, parent: Value, ref: Any, value_type: Type | UnionType, metadata: Metadata | None = None
    ) -> Value:
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
        raise UnsupportedValueType(qual_name=value.qual_name, value_type=value.type)

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

    def load(self, env: "VarBinding", value: Value) -> Any:
        """Shorthand method for loading values."""
        loader: Loader = self.resolve_loader(value)
        return loader.load(env, value, self)


@dataclass
class BindingChanges:
    """Summary of changes in value bindings."""

    # The motivation behind the footprint is the following.
    # Some of the value types may produce a type-specific
    # default value. Examples are: optionals, empty lists,
    # empty any-length tuples, data-class with all fields
    # having default values, any combination of those, etc.
    # In such cases type-specific default values are produced
    # without binding any environment variables.
    # There are certain cases in which we need to know if
    # the value was produced without consuming any variables:

    footprint: int  # Amount of variables consumed


@dataclass
class VarBinding:
    """Environment variables mapped to the corresponding values."""

    vars: Mapping[str, str]
    bound: Dict[str, Value] = dataclasses.field(default_factory=dict)

    def bind(self, value: Value):
        """Bind variable to the given value"""
        if value.var_name not in self.vars:
            raise MissingRequiredVar(value.var_name, value.qual_name)
        if value.var_name in self.bound:
            other = self.bound[value.var_name]
            raise AmbiguousVarError(value.var_name, other.qual_name, value.qual_name)
        self.bound[value.var_name] = value

    @contextmanager
    def track_changes(self) -> Iterator[BindingChanges]:
        """Track binding changes."""
        bound_before: int = len(self.bound)
        changes = BindingChanges(0)
        yield changes
        bound_after: int = len(self.bound)
        changes.footprint = bound_after - bound_before


class Loader(abc.ABC):
    """Loader encapsulate type-specific loading logic."""

    @abstractmethod
    def can_load(self, value: Value) -> bool:
        """Check if loader can handle the value."""

    @abstractmethod
    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> Any:
        """Do load value from the environment variables."""

    @abstractmethod
    def is_present(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Check if ALL variables required to successfully load the value are defined."""


class BasicValueLoader(Loader):
    """Loader for basic value types.

    This is one of the loaders that actually consumes env variables
    to load the value. Basic value is assumed to be atomic so the
    loader always consumes exactly 1 variable.
    """

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
        try:
            return self.type(raw_value)
        except ValueError as error:
            raise InvalidVariableFormat(value.var_name, value.qual_name, cause=str(error))

    def is_present(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Check if value is represented by the given environment variables."""
        return value.var_name in env.vars


class BooleanLoader(BasicValueLoader):
    """A basic value loader for boolean values."""

    def __init__(self):
        super().__init__(bool)

    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Load boolean value."""
        env.bind(value)
        raw_value: str = env.vars[value.var_name].upper()
        normalized: str = raw_value.upper().strip()
        if normalized == "TRUE" or normalized == "1" or normalized == "YES":
            return True
        elif normalized == "FALSE" or normalized == "0" or normalized == "NO":
            return False
        raise InvalidVariableFormat(value.var_name, value.qual_name, cause=f"invalid boolean format: '{raw_value}'")


class CustomLoader(Loader):
    """Loader for values with custom user-specified formats.

    The loader uses the `load` attribute of the field metadata.
    """

    def can_load(self, value: Value) -> bool:
        """Check if custom loader is defined."""
        return value.metadata is not None and value.metadata.load is not None

    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> Any:
        """Do load the value with a custom loader."""
        env.bind(value)
        try:
            return value.metadata.load(env.vars[value.var_name])
        except ValueError as error:
            raise InvalidVariableFormat(value.var_name, value.qual_name, cause=str(error))

    def is_present(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Check if the corresponding variable is defined."""
        return value.var_name in env.vars


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
            has_default = DataClasses.has_default(field)
            if has_default and not is_present:
                continue

            # If the field is required but not present, exception should be raised by any of
            # the downstream loaders, so the error message will be as specific as possible.
            # That's why we shouldn't raise MissingRequiredVar exception here and should
            # always try to load the value instead.

            with env.track_changes() as changes:
                loaded_value = field_loader.load(env, field_value, strategy)

            # Some of the value types (like nullables and lists) may be successfully loaded
            # without consuming any environment variables. In such cases the  produced value
            # is type-specific default. On the other hand the data-class field may also
            # specify its own default value. In such case the field-specific default must be
            # used instead of the type-specific one:

            if changes.footprint == 0 and has_default:
                loaded_value = DataClasses.default_value(field)

            constructor_arguments[field.name] = loaded_value
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
            field_loader = strategy.resolve_loader(field_value)
            if not field_loader.is_present(env, field_value, strategy):
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
        raise UnionLoadingError(qual_name=value.qual_name, value_type=value.type)

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

    LENGTH_ATTR: str = "LEN"

    def can_load(self, value: Value) -> bool:
        """Check if the value type is list."""
        origin = typing.get_origin(value.type)
        return value == list or origin is list or origin is List or origin is typing.Sequence

    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> List:
        """Do load list value."""
        # Check if length is specified explicitly
        length_value = strategy.child_value(value, self.LENGTH_ATTR, int | None)
        length: int | None = strategy.load(env, length_value)

        items: List = []
        item_type: Type = self._item_type(value)
        current_index: int = 0
        current_item: Value = strategy.child_value(value, current_index, item_type)
        item_loader: Loader = strategy.resolve_loader(current_item)
        while item_loader.is_present(env, current_item, strategy) or (length and current_index < length):
            with env.track_changes() as changes:
                loaded_item_value = item_loader.load(env, current_item, strategy)

            # Continue until the next item could be loaded (i.e. it is present)
            # AND until the item actually consumes environment variables.
            # Otherwise, we may end up loading infinitely many type-specific
            # default values for the list's item type.
            if changes.footprint == 0:
                break

            items.append(loaded_item_value)
            current_index += 1
            current_item = strategy.child_value(value, current_index, item_type)
        return items

    @staticmethod
    def _item_type(value: Value) -> Type:
        """Get item type."""
        type_args: Tuple[Type, ...] = typing.get_args(value.type)
        if not type_args:
            raise UnsupportedValueType(qual_name=value.qual_name, value_type=value.type)
        return type_args[0]

    def is_present(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Check if list is present."""
        return True  # List may be empty in which case it is also present.


class FixedLengthTupleLoader(Loader):
    """Fixed-length tuples loader."""

    def can_load(self, value: Value) -> bool:
        """Check if value is a fixed-length tuple."""
        return Tuples.is_fixed(value.type)

    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> Any:
        """Do load fixed-length tuple."""
        items: List[Any] = []
        item_types = typing.get_args(value.type)
        for index, item_type in enumerate(item_types):
            item = strategy.child_value(value, index, item_type)
            item_loader = strategy.resolve_loader(item)
            loaded_value = item_loader.load(env, item, strategy)
            items.append(loaded_value)
        return tuple(items)

    def is_present(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Check if fixed-length tuple is correctly represented by the variables."""
        item_types = typing.get_args(value.type)
        for index, item_type in enumerate(item_types):
            item = strategy.child_value(value, index, item_type)
            item_loader = strategy.resolve_loader(item)
            if not item_loader.is_present(env, item, strategy):
                return False
        return True


class AnyLengthTupleLoader(Loader):
    """Any-length tuples loader."""

    LENGTH_ATTR: str = "LEN"

    def can_load(self, value: Value) -> bool:
        """Check if value type is tuple."""
        return Tuples.is_any_length(value.type)

    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> Any:
        """Do load the tuple."""
        # Check if length is specified explicitly
        length_value = strategy.child_value(value, self.LENGTH_ATTR, int | None)
        length: int | None = strategy.load(env, length_value)

        item_type = Tuples.item_type(value.type)
        current_index: int = 0
        current_item: Value = strategy.child_value(value, current_index, item_type)
        item_loader: Loader = strategy.resolve_loader(current_item)
        items: List[Any] = []
        while item_loader.is_present(env, current_item, strategy) or (length and current_index < length):
            with env.track_changes() as changes:
                loaded_item_value = item_loader.load(env, current_item, strategy)

            # Continue until the next item could be loaded (i.e. it is present)
            # AND until the item actually consumes environment variables.
            # Otherwise, we may end up loading infinitely many type-specific
            # default values for the tuple's item type.
            if changes.footprint == 0:
                break

            items.append(loaded_item_value)
            current_index += 1
            current_item: Value = strategy.child_value(value, current_index, item_type)
        return tuple(items)

    def is_present(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Check if tuple is present."""
        return True  # Tuple may be empty in which case no variables are required


class OptionalLoader(Loader):
    """Optional value loader."""

    IS_NONE: str = "IS_NONE__"

    def can_load(self, value: Value) -> bool:
        """Check if type is optional."""
        return OptionalTypes.is_optional(value.type)

    def load(self, env: VarBinding, value: Value, strategy: Strategy) -> Any:
        """Load optional value."""
        # Check if optional value is explicitly set to None
        is_none_value = strategy.child_value(value, OptionalLoader.IS_NONE, str)
        is_none_loader = strategy.resolve_loader(is_none_value)
        if is_none_loader.is_present(env, is_none_value, strategy):
            is_none_loader.load(env, is_none_value, strategy)
            return None

        # Otherwise, load the optional value if it is present
        actual_type = OptionalTypes.remove_optional(value.type)
        actual_value = dataclasses.replace(value, type=actual_type)
        loader = strategy.resolve_loader(actual_value)
        if loader.is_present(env, actual_value, strategy):
            with env.track_changes() as changes:
                loaded_value = loader.load(env, actual_value, strategy)

            # The actual child-type may have its own type-specific default value.
            # In such a case the optional value must be None.

            if changes.footprint > 0:
                return loaded_value

        return None

    def is_present(self, env: VarBinding, value: Value, strategy: Strategy) -> bool:
        """Check if value is present."""
        return True  # Optional value may be loaded without consuming any variables


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
    FixedLengthTupleLoader(),
    AnyLengthTupleLoader(),
)
