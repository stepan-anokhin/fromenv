import abc
import dataclasses
from abc import abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import Optional, Type, Any, Dict, Sequence, Tuple

from fromenv.errors import UnsupportedValueType, MissingRequiredVar, AmbiguousVarError
from fromenv.internal.data import DataClasses


@dataclass(frozen=True)
class Config:
    prefix: str | None = None  # Common prefix
    sep: str = '_'  # Separator between variable name parts
    loaders: Sequence["Loader"] | None = None


class Value:
    """This class represents an abstract value encoded by environment variables.

    Value instances form a tree reflecting actual data structure (where values representing
    data structures or collections may have child values and values representing basic data
    types will always be a leafs).
    """

    ref: Any  # Field name, list index or key by which the value is referenced
    type: Type  # Actual value type
    parent: Optional["Value"]  # Parent value
    config: Config
    consumed: Dict[str, "Value"]  # Variable names consumed by some values, shared across all values in the tree.
    loader: "Loader"

    def __init__(
            self,
            ref: Any,
            value_type: Type,
            parent: Optional["Value"] = None,
            config: Config = None,
            consumed: Dict[str, "Value"] | None = None,
            loader: "Loader" = None,
    ):
        self.ref = ref
        self.type = value_type
        self.parent = parent
        self.config = config or Config()
        self.consumed = consumed or {}
        self.loader = loader or self._resolve_loader()

    def _resolve_loader(self) -> "Loader":
        """Resolve appropriate value loader."""
        loaders = self.config.loaders or DEFAULT_LOADERS
        for loader in loaders:
            if loader.can_load(self.type):
                return loader
        raise UnsupportedValueType(f"Value type is not supported: {self.type}")

    def consume(self):
        """Consume variable name."""
        if self.var_name in self.consumed:
            other = self.consumed[self.var_name]
            raise AmbiguousVarError(f"Variable '{self.var_name}' matched to multiple values:\n\t{self}\n\t{other}")
        self.consumed[self.var_name] = self

    def load(self, env: Dict[str, str]) -> Any:
        """Load value from the variables."""
        return self.loader.load(env, self)

    def exists(self, env: Dict[str, str]) -> bool:
        """Check if value is represented by the given environment variables."""
        return self.loader.exists(env, self)

    def nested(self, ref: Any, value_type: Type) -> "Value":
        """Create nested value."""
        return Value(
            ref=ref,
            value_type=value_type,
            parent=self,
            config=self.config,
            consumed=self.consumed,
        )

    @cached_property
    def var_name(self) -> str:
        """Get the corresponding variable name."""
        if self.parent is None:
            return self.config.prefix
        this_name = str(self.ref).upper()
        if self.parent.var_name is None:
            return this_name
        else:
            return f'{self.parent.var_name}{self.config.sep}{this_name}'

    @cached_property
    def repr(self) -> str:
        """Human-readable representation."""
        if self.parent is None:
            return self.type.__name__
        if DataClasses.is_dataclass(self.parent.type):
            return f'{self.parent.repr}.{self.ref}'
        return f'{self.parent.repr}[{self.ref}]'

    def __repr__(self) -> str:
        """Get human-readable representation."""
        return self.repr


class Loader(abc.ABC):
    """Abstract base class for value loaders."""

    @abstractmethod
    def can_load(self, value_type: Type) -> bool:
        """Check if the loader can handle the given value type."""

    @abstractmethod
    def load(self, env: Dict[str, str], value: Value) -> Any:
        """Do load value from the environment variables."""

    @abstractmethod
    def exists(self, env: Dict[str, str], value: Value) -> bool:
        """Check if value is present among the given environment variables."""


class BasicValueLoader(Loader):
    """Base class for basic value loaders."""
    type: Type

    def __init__(self, value_type: Type):
        self.type = value_type

    def can_load(self, value_type: Type) -> bool:
        """Check if the given value type could be handled."""
        return value_type is self.type

    def load(self, env: Dict[str, str], value: Value) -> Any:
        """Do load value."""
        value.consume()
        return self.type(env[value.var_name])

    def exists(self, env: Dict[str, str], value: Value) -> bool:
        """Check if value is represented by the given environment variables."""
        return value.var_name in env


class BooleanLoader(BasicValueLoader):
    """Boolean value loader."""

    def __init__(self):
        super().__init__(bool)

    def load(self, env: Dict[str, str], value: Value) -> bool:
        """Load boolean value."""
        value.consume()
        raw_value: str = env[value.var_name]
        return raw_value.upper() == "TRUE" or raw_value == "1"


class DataClassLoader(Loader):
    """Data class loader."""

    def can_load(self, value_type: Type) -> bool:
        """Check if the requested value type is a data class."""
        return DataClasses.is_dataclass(value_type)

    def load(self, env: Dict[str, str], value: Value) -> Any:
        """Do load data class instance."""
        constructor_arguments: Dict[str, Any] = {}
        for field in dataclasses.fields(value.type):
            nested = value.nested(field.name, field.type)
            exists = nested.exists(env)
            if DataClasses.is_required(field) and not exists:
                raise MissingRequiredVar(f"Required field is missing: {nested}")
            if exists:
                constructor_arguments[field.name] = nested.load(env)
        return value.type(**constructor_arguments)

    def exists(self, env: Dict[str, str], value: Value) -> bool:
        """Check if required fields are present."""
        for field in DataClasses.required_fields(value.type):
            if not value.nested(field.name, field.type).exists(env):
                return False
        return True


DEFAULT_LOADERS: Tuple[Loader, ...] = (
    BasicValueLoader(int),
    BasicValueLoader(float),
    BasicValueLoader(str),
    BooleanLoader(),
    DataClassLoader(),
)
