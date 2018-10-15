"""Support for regular expression based lexing

This module provides text lexing (a.k.a. tokenization, scanning) facilities
based on regular expressions as defined in the standard `re` module.

It is intended for use as a lightweight and portable first step in the
processing of programming languages. It is ideal for use in tools such as code
formatters, identifier renamers, or various data extractors (e.g. get list of
files included in a C++ source).

A lexer is an instance of the `Lexer` class. Lexers contain a compiled
regular expression and other data associated with the defined tokens. The
`Lexer.tokens` method generates a sequence of `Token` objects as read from an
input string.

Failing to match any of the specified regular expression patterns is not an
error, but instead produces a token indicating no match.
"""

import functools
import re
from typing import Dict, Iterator, List, NamedTuple, Optional, Sequence, Tuple
import uuid


class Token(NamedTuple):
    """A lexical token parsed from input text"""
    # name of the token kind passed into the lexer, e.g. 'quoted string', or
    # `None` if this section of text did not match any token pattern
    kind: Optional[str]

    # complete input text that matched the token pattern, or that didn't match
    # any token pattern
    text: str

    # list of values of captured subgroups within the token pattern. If a
    # subgroup did not match, then its value is `None`
    groups: List[Optional[str]]

    # half-open range of indicies indicating where within the input string
    # this token occurred
    input_range: slice


class _GroupSpec(NamedTuple):
    """Information about a regex subpattern corresponding to a token"""
    # index within the combined regex's group list corresponding to the full
    # match of this token.
    group_index: int

    # half-open range of indicies within the combined regex's group list
    # corresponding to the capturing subgroups of this token, e.g. `(3, 5)` if
    # there are subgroups at indicies `3` and `4`, or `(4, 4)` if there are
    # no capturing subgroups.
    subgroup_range: slice

    # name of this token, as originally specified during the lexer's
    # initialization, e.g. 'quoted string'
    token_kind: str


def _intify(integer: Optional[int]) -> int:
    """mypy is so stupid that it thinks `slice.stop` is optional. It's not."""
    assert integer is not None
    return integer


def _token_pattern_to_group_spec(
        spec_list: List[_GroupSpec],
        named_pattern: Tuple[str, str]) -> List[_GroupSpec]:
    "Append a group spec from the named pattern and return the extended list."
    # If we're the first pattern, then our groups' indicies within the list of
    # groups of the combined pattern will start at zero. Otherwise, the
    # indicies are offset by the end of the previous index.
    if len(spec_list) == 0:
        index = 0
    else:
        index = _intify(spec_list[-1].subgroup_range.stop)

    name, pattern = named_pattern
    num_subgroups = re.compile(pattern).groups

    spec_list.append(
        _GroupSpec(
            group_index=index,
            subgroup_range=slice(index + 1, index + 1 + num_subgroups),
            token_kind=name))

    return spec_list


def _group_specs(token_patterns: Dict[str, str]) -> List[_GroupSpec]:
    return functools.reduce(_token_pattern_to_group_spec,
                            token_patterns.items(), [])


def _combine_patterns(patterns: Sequence[str]) -> str:
    return '|'.join(f'({pattern})' for pattern in patterns)


class Lexer:
    def __init__(self, token_patterns: Dict[str, str]) -> None:
        """`token_patterns` maps a token's name to its regex pattern."""
        self._regex = re.compile(
            _combine_patterns(list(token_patterns.values())))
        self._group_specs = _group_specs(token_patterns)

    def tokens(self, text: str) -> Iterator[Token]:
        """Generate a sequence of tokens read from input text."""
        index = 0
        end = len(text)

        while index != end:
            assert index < end
            match = self._regex.search(text, index, end)
            if match is None:
                span = slice(index, end)
                yield Token(
                    kind=None, text=text[span], groups=[], input_range=span)
                index = end
            else:
                start = match.start()
                # if there was some unmatched text after index
                if start != index:
                    span = slice(index, start)
                    yield Token(
                        kind=None,
                        text=text[span],
                        groups=[],
                        input_range=span)

                # find out which token was matched
                groups = match.groups()
                matched_spec = next(spec for spec in self._group_specs
                                    if groups[spec.group_index] is not None)
                span = slice(start, match.end())

                yield Token(
                    kind=matched_spec.token_kind,
                    text=groups[matched_spec.group_index],
                    groups=list(groups[matched_spec.subgroup_range]),
                    input_range=span)

                index = _intify(span.stop)


def tokenize(text: str, token_patterns: Dict[str, str]) -> Iterator[Token]:
    """Generate a sequence of tokens read from `text`.

    Create a `Lexer` using `token_patterns`, and then use the lexer to generate
    tokens read from `text`.
    """
    return Lexer(token_patterns).tokens(text)
