"""Exceptions raised by proctree.

The formatting in ParseError._format mirrors what CPython's own tokenizer
does for SyntaxError: show the offending line and put a caret under the
exact column, instead of just naming a line number and leaving the reader
to go count characters.
"""


class ProcessTreeError(Exception):
    """Base class for all errors raised by this library."""


class ParseError(ProcessTreeError):
    def __init__(self, message: str, line: int, column: int, source_line: str):
        self.message = message
        self.line = line
        self.column = column
        self.source_line = source_line
        super().__init__(self._format())

    def _format(self) -> str:
        gutter = str(self.line)
        pad = " " * len(gutter)
        pointer = " " * (self.column - 1) + "^"
        return (
            f"{self.message} (line {self.line}, column {self.column})\n"
            f"    {gutter} | {self.source_line}\n"
            f"    {pad} | {pointer}"
        )
