"""Encode python values as SQL literals.

This module provides a function, `to_sql`, that converts a specified python
object into a string suitable for splicing into a SQL statement.

It notably does not support date and time related types, since those are a pain
in the ass to do portably across databases.
"""

import numbers
from typing import Any


def to_sql(value: Any) -> str:
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    elif isinstance(value, numbers.Real):
        return str(value)
    elif isinstance(value, list):
        return '(' + ', '.join(to_sql(element) for element in value) + ')'
    elif value is None:
        return 'null'
    else:
        raise Exception(f'to_sql called with value of unsupported type '
                        f'{type(value)}. The value was: {value}')
