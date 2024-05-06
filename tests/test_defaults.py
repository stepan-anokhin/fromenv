"""
The from_env(DataClass) API works by inspecting data types.
Some data types may produce values without consuming any
environment variables. Such values are called "type-specific
defaults" and denoted as "default(T)" for type T throughout
library documentation. Also, data class fields may have default
values. Those are called "field-specific defaults" and denoted
as "default(field)".

In some situations multiple different values of the same type
may be produced without consuming any environment variables.
The following convention is used to unambiguously determine
which default value should be produced:
1. If there is a field F of the type T, and default(F) is defined,
    then default(F) should be used instead of default(T)
2. default(Optional[T]) is always None
3. default(List[T]) is always empty list []
4. default(Tuple[T, ...]) is always empty tuple ()
5. default(Tuple[T1, ..., Tn]) is a tuple of defaults
   (default(T1), ..., default(Tn))

This test-module checks if the above convention is correctly
implemented.
"""
