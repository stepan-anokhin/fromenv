from dataclasses import dataclass
from typing import Callable, Any


@dataclass
class Metadata:
    """User-supplied field metadata."""

    name: str | None = None
    load: Callable[[str], Any] | None = None
