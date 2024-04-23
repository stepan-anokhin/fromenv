"""Type aliases used across the library."""

from typing import TypeAlias, Callable, Tuple, Dict, TypeVar, Any

T = TypeVar("T")

Predicate: TypeAlias = Callable[[T], bool]
DictItem: TypeAlias = Tuple[Any, Any]
DictQuery: TypeAlias = Predicate[DictItem]
EnvDict: TypeAlias = Dict[str, str]
