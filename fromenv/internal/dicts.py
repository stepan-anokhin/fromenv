"""Provides utility-functions to work with dictionaries."""

import re

from fromenv.internal.types import DictQuery, DictItem, EnvDict


class Dicts:
    """Dict utilities."""

    @staticmethod
    def prefix(prefix: str) -> DictQuery:
        """Create a predicate that returns True iff entry key starts with the given prefix."""

        def predicate(entry: DictItem) -> bool:
            """Check key has prefix."""
            key, _ = entry
            return isinstance(key, str) and key.startswith(prefix)

        return predicate

    @staticmethod
    def pattern(pattern: str) -> DictQuery:
        """Make predicate to select dict items with keys matching the regex pattern."""

        compiled_pattern: re.Pattern = re.compile(pattern)

        def predicate(entry: DictItem) -> bool:
            """Check pattern against entry key."""
            key, _ = entry
            return isinstance(key, str) and bool(compiled_pattern.match(key))

        return predicate

    @staticmethod
    def select(env: EnvDict, query: DictQuery) -> EnvDict:
        """Select dict subset."""
        return dict(filter(query, env.items()))

    @staticmethod
    def any(env: EnvDict, query: DictQuery) -> bool:
        """Check if any entry satisfies query."""
        return any(map(query, env.items()))
