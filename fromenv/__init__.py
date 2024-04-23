import os
from dataclasses import dataclass
from typing import Type, Dict, TypeVar

from fromenv.errors import MissingRequiredVar, AmbiguousVarError
from fromenv.internal.data import DataClasses
from fromenv.internal.dicts import Dicts
from fromenv.internal.value import Config, Value

T = TypeVar("T")


def from_env(data_class: Type[T], env: Dict[str, str] | None = None, config: Config | None = None) -> T:
    """Load data class instance from environment variables."""
    if not DataClasses.is_dataclass(data_class):
        raise ValueError(f"Not a data class: {data_class}")

    env = env or os.environ

    root_value = Value(ref=None, value_type=data_class, config=config)
    return root_value.load(env)


@dataclass
class Server:
    host: str
    port: str
    retries: int


@dataclass
class ServiceConfig:
    secret_path: str
    server: Server
    optional_property: int = 10


if __name__ == "__main__":
    cfg = from_env(ServiceConfig, )
    print(cfg)
