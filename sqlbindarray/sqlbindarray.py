"""Expand array-valued bindings into SQL statements

This module provides a function, `replace`, that transforms a SQL statement to
include literal array values for a specified set of named parameters.
"""

import enum
from typing import Any, Iterator, Mapping, Optional, Tuple, Union

from . import encode
from . import lexer

_token_patterns = {
    'quoted string': r"'[^']*'",
    'quoted identifier': r'"([^"]*)"',  # capture what's inside
    'line comment': r'--[^\n]*(?:\n|$)',
    'block comment': r'/\*+(?:[^*]|\*[^/])*\*+/',
    'named parameter prefix': r'[:@]',
    'named parameter length prefix': r'#:|#@',
    'python named parameter': r'%\((\w+)\)s',  # capture what's inside
    'python named parameter length': r'#%\((\w+)\)s',  # capture what's inside
    'word': r'\w+',
    'whitespace': r'\s+'
}

# This `Lexer` object is lazily loaded by the `_tokens` function.
_lexer_singleton: Optional[lexer.Lexer] = None


def _tokens(text: str) -> Iterator[lexer.Token]:
    """Generate tokens from `text` using a singleton instance of `lexer.Lexer`.
    """
    global _lexer_singleton
    if _lexer_singleton is None:
        _lexer_singleton = lexer.Lexer(_token_patterns)

    return _lexer_singleton.tokens(text)


"""Some named parameters consist of two tokens, e.g.

    @foo

is 'named parameter prefix' followed by 'word', and

    :"foo"

is 'named parameter prefix' followed by 'quoted identifier', and

    #@bar

is 'named parameter length prefix' followed by 'word'.

Other named parameters consist of only one token, e.g.

    %(foo)s

is just 'python named parameter', and

    #%(foo)s

is just 'python named parameter length'.

Because of this, in order to match all sequences of tokens that match a
named parameter or named parameter length, the parser has to be a state
machine. The machine has three states, enumerated in the `_ParserState`
class. The function `_handle_token` takes a state value, a token, and a
mapping of named parameter bindings, and returns an "output operation," a
string possibly to append to the output, and a new (or possibly the same)
state value. The parser can then iterate through input tokens, updating the
state and output as necessary, until no input remains.

Below is a table illustrating the state transitions implemented by
`_handle_token`:
```
 -----------------------------------------------------------------------------
| Current State       | Token Kind         | Output Op  | New State           |
| -------------       | ----------         | ---------  | ---------           |
| CHILLIN             | python param       | FLUSH      | CHILLIN             |
| CHILLIN             | python param len   | FLUSH      | CHILLIN             |
| CHILLIN             | param prefix       | PUSH       | IN_PARAMETER        |
| CHILLIN             | param len prefix   | PUSH       | IN_PARAMETER_LENGTH |
| CHILLIN             | <other>            | FLUSH      | CHILLIN             |
| IN_PARAMETER        | word               | EMIT/FLUSH | CHILLIN             |
| IN_PARAMETER        | quoted identifier  | EMIT/FLUSH | CHILLIN             |
| IN_PARAMETER        | <other>            | !!!        | !!!                 |
| IN_PARAMETER_LENGTH | word               | EMIT/FLUSH | CHILLIN             |
| IN_PARAMETER_LENGTH | quoted identifier  | EMIT/FLUSH | CHILLIN             |
| IN_PARAMETER_LENGTH | <other>            | !!!        | !!!                 |
 ----------------------------------------------------------------------------- 
```

The values of the "Output Op" column have the following meanings:

TODO: Describe when EMIT is used and when FLUSH is used.
"""


class _ParserState(enum.Enum):
    """Possible states of the named parameter parser"""
    # The default state. Can accept any token kind from this state.
    CHILLIN = 0
    # A prefix was just read ('@', ':'). Looking for parameter name.
    IN_PARAMETER = 1
    # A length prefix was just read ('#@', '#:'). Looking for parameter name.
    IN_PARAMETER_LENGTH = 2


class _OutputOperation(enum.Enum):
    # Enqueue the associated text for future output or discard.
    PUSH = 0
    # Output the associated text and discard any enqueued text.
    EMIT = 1
    # Output any enqueued text, and then output the associated text.
    FLUSH = 2


def _handle_token(token: lexer.Token, state: _ParserState,
                  bindings: Mapping[str, Any]
                  ) -> Tuple[_OutputOperation, str, _ParserState]:
    """State machine transition function driven by a token"""
    Ops = _OutputOperation
    States = _ParserState
    kind, text, groups, *_ = token

    if kind in ('line comment', 'block comment', 'whitespace'):
        return Ops.PUSH, text, state

    if state == States.CHILLIN:
        if kind == 'python named parameter':
            name, = groups
            assert name is not None
            if name in bindings:
                return Ops.FLUSH, encode.to_sql(bindings[name]), state
            else:
                return Ops.FLUSH, text, state
        elif kind == 'python named parameter length':
            name, = groups
            assert name is not None
            if name in bindings:
                return Ops.FLUSH, str(len(bindings[name])), state
            else:
                return Ops.FLUSH, text, state
        elif kind == 'named parameter prefix':
            return Ops.PUSH, text, States.IN_PARAMETER
        elif kind == 'named parameter length prefix':
            return Ops.PUSH, text, States.IN_PARAMETER_LENGTH
        else:
            return Ops.FLUSH, text, state
    else:
        if kind == 'word':
            name = text
        elif kind == 'quoted identifier':
            name, = groups
        else:
            raise Exception(f'Unexpected token {token} following named '
                            'parameter prefix character. Expected to see '
                            'a parameter name instead.')

        assert name is not None

        if name not in bindings:
            return Ops.FLUSH, text, States.CHILLIN
        elif state == States.IN_PARAMETER:
            return Ops.EMIT, encode.to_sql(bindings[name]), States.CHILLIN
        else:
            assert state == States.IN_PARAMETER_LENGTH
            return Ops.EMIT, str(len(bindings[name])), States.CHILLIN


def replace(sql_statement: str, bindings: Mapping[str, Any]) -> str:
    """Replace named parameters with python values in a SQL statement.

    Return a modified copy of `sql_statement` for which named parameters found
    in `bindings` have been replaced by their values in `bindings`.
    Additionally, any named parameter preceded by the '#' character will be
    replaced by the length of its value in `bindings`, rather than by the value
    itself.
    """
    output_parts = []
    enqueued_parts = []
    state = _ParserState.CHILLIN

    for token in _tokens(sql_statement):
        op, part, state = _handle_token(token, state, bindings)
        if op == _OutputOperation.PUSH:
            enqueued_parts.append(part)
        elif op == _OutputOperation.EMIT:
            output_parts.append(part)
            enqueued_parts.clear()
        else:
            assert op == _OutputOperation.FLUSH
            output_parts.extend(enqueued_parts)
            output_parts.append(part)
            enqueued_parts.clear()

    output_parts.extend(enqueued_parts)
    return ''.join(output_parts)
