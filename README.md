# fromenv

A module to initialize nested data classes ([PEP 557](https://peps.python.org/pep-0557/))
from environment variables (or any plain dict).

## Installation

```shell
pip install fromenv
```

## Requirements

Python version `>=3.8.1`

## Quick Start

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

## Completeness

### Context

In general, we want that for every possible value $V$ of any supported type $T$
there should be such a combination of environment variables that will correspond
exactly to this value $V$. We will call this desirable property a "completeness".
And our goal is to make `from_env(T, env)` API "complete" in this sense.

### The Problem

If some environment variables $v\_1, ..., v\_n$ were used to load value $V$
then we say that $v1, ..., vn$ were "consumed" by the value $V$, and the
full set $\set{v\_1, ..., v\_n}$ of those variables we call a "footprint" of
value $V$ (and denote it $footprint(V)$ throughout the documentation).

In some cases multiple values $V_1, ..., V_n$ of type `T` could be produced
with $footprint(V_1) = ... = footprint(V_n) = \emptyset$. Such values
are called "defaults". Conventions for type `T` will define which value
from possible defaults $V_1, ..., V_n$ will be produced.
But how do we achieve completeness in such cases?

### Solution

For each possible default value there should be a way to produce
it by consuming at least one variable. `from_env()` provides the
following ways to do that: 

1. For lists and tuples of any length we may explicitly specify
   length = 0 to get empty list or empty tuple correspondingly.
   If `VAR_NAME_<index>` variables are expected to represent
   list or tuple items, then we may set `VAR_NAME_LEN=0` to
   specify empty array or tuple.
2. For `Optional[T]` to produce None we define `IS_NONE__` attribute:
   if `VAR_NAME` variable represents `Optional[T]` value, then
   `VAR_NAME_IS_NONE__` variable indicates that `None` should be produced.
3. For data class with all fields having default values simply explicitly
   specify default value for any field.