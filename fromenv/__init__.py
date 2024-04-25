import os
from dataclasses import dataclass
from typing import Type, Dict, TypeVar

from fromenv.errors import MissingRequiredVar, AmbiguousVarError
from fromenv.internal.data_classes import DataClasses
from fromenv.internal.dicts import Dicts
from fromenv.internal.value import Config, Value, Strategy, VarBinding

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
    cfg = from_env(ServiceConfig, {"SECRET_PATH": "/some/path", "SERVER_HOST": "example.com", "SERVER_PORT": "8080",
                                   "SERVER_RETRIES": "10"})
    print(cfg)
