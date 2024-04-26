import os
from typing import Type, Dict, TypeVar

from fromenv.errors import MissingRequiredVar, AmbiguousVarError
from fromenv.internal.data_classes import DataClasses
from fromenv.internal.dicts import Dicts
from fromenv.internal.loaders import Config, Value, Strategy, VarBinding

# Specify exported symbols
__all__ = (
    "from_env",
    "Config",
    "MissingRequiredVar",
    "AmbiguousVarError",
)

T = TypeVar("T")


def from_env(data_class: Type[T], env: Dict[str, str] | None = None, config: Config | None = None) -> T:
    """Load data class instance from environment variables."""
    if not DataClasses.is_dataclass(data_class):
        raise ValueError(f"Not a data class: {data_class}")

    env = env or os.environ

    config = config or Config()
    strategy = Strategy(config)
    root_value = strategy.root_value(data_class)
    loader = strategy.resolve_loader(root_value)
    return loader.load(VarBinding(env), root_value, strategy)
