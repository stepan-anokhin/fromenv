# fromenv

A module to initialize nested data classes ([PEP 557](https://peps.python.org/pep-0557/))
from environment variables (or any plain dict).

# Installation

```shell
pip install fromenv
```

# Requirements

Python version `^3.6`

# Quick Start

```python
import os
from dataclasses import dataclass

from fromenv import from_env


@dataclass
class Server:
    port: int
    host: str


@dataclass
class Config:
    cert_path: str
    server: Server


def main():
    print(os.environ)
    # >>> {
    #   'CERT_PATH': '/some/path', 
    #   'SERVER_HOST': 'example.com', 
    #   'SERVER_PORT':'8080',
    #   ...
    # }

    config: Config = from_env(data_class=Config)
```
