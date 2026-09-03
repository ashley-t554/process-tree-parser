"""Parser for the indentation-based process tree text format.

A line is `<pid> <name>`, and a line's depth in the tree is determined by
how far it is indented relative to the line above it, the same way a YAML
or Python block is read. Indentation width does not have to be uniform
across the whole file, only consistent within one nesting step, so both

    1 init
      100 sshd

and

    1 init
        100 sshd

are valid. Blank lines and lines starting with '#' (after indentation)
are ignored.
"""

from .errors import ParseError
from .tree import Process


def _leading_whitespace(raw: str) -> str:
    i = 0
    while i < len(raw) and raw[i] in (" ", "\t"):
        i += 1
    return raw[:i]


def _parse_pid_and_name(rest: str, indent: int, lineno: int, raw: str) -> tuple[int, str]:
    i = 0
    n = len(rest)
    while i < n and not rest[i].isspace():
        i += 1
    pid_str = rest[:i]

    if not pid_str:
        raise ParseError("expected a pid at the start of the line", lineno, indent + 1, raw)
    if not pid_str.isdigit():
        raise ParseError(
            f"expected an integer pid, found {pid_str!r}", lineno, indent + 1, raw
        )

    j = i
    while j < n and rest[j].isspace():
        j += 1
    name = rest[j:].rstrip()

    if not name:
        raise ParseError(
            "expected a process name after the pid", lineno, indent + j + 1, raw
        )

    return int(pid_str), name


def parse(text: str) -> list[Process]:
    """Parse process tree text into a forest of root Process nodes."""
    roots: list[Process] = []
    stack: list[tuple[int, Process]] = []
    seen_pids: dict[int, int] = {}

    for lineno, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue

        leading = _leading_whitespace(raw)
        if "\t" in leading:
            column = leading.index("\t") + 1
            raise ParseError(
                "tabs are not allowed in indentation; use spaces instead",
                lineno,
                column,
                raw,
            )

        indent = len(leading)
        rest = raw[indent:]
        if rest.startswith("#"):
            continue

        pid, name = _parse_pid_and_name(rest, indent, lineno, raw)

        if pid in seen_pids:
            raise ParseError(
                f"pid {pid} was already used on line {seen_pids[pid]}",
                lineno,
                indent + 1,
                raw,
            )
        seen_pids[pid] = lineno

        node = Process(pid=pid, name=name, line=lineno)

        while stack and indent < stack[-1][0]:
            stack.pop()
        if stack and indent == stack[-1][0]:
            stack.pop()

        if stack:
            parent = stack[-1][1]
            parent.children.append(node)
            node.parent = parent
        else:
            if indent != 0:
                raise ParseError(
                    "unexpected indentation; no enclosing process at this level",
                    lineno,
                    indent + 1,
                    raw,
                )
            roots.append(node)

        stack.append((indent, node))

    return roots


def parse_file(path) -> list[Process]:
    """Read a file and parse it as process tree text."""
    with open(path, "r", encoding="utf-8") as handle:
        return parse(handle.read())
