"""Parser for `ps -ef` and `ps -ef --forest` output.

ps prints one process per line under a fixed set of whitespace-separated
columns, with CMD last since it's the only column that can itself contain
spaces. --forest additionally indents CMD and prefixes children with a
`\\_` marker, but that's cosmetic: the real parent/child relationship is
the PPID column. This parser rebuilds the tree from PID/PPID pairs and
strips the forest decoration rather than reading it, so it accepts output
from `ps -ef` with or without --forest, and doesn't care what order the
lines come in.
"""

import re

from .errors import ParseError
from .tree import Process

_TOKEN_RE = re.compile(r"\S+")
_FOREST_MARKER = "\\_"


def _tokens(raw: str) -> list[re.Match]:
    return list(_TOKEN_RE.finditer(raw))


def _find_header_columns(raw: str, lineno: int) -> tuple[int, int, int]:
    columns = [m.group() for m in _tokens(raw)]
    if not columns:
        raise ParseError("expected a ps header line", lineno, 1, raw)

    try:
        pid_col = columns.index("PID")
        ppid_col = columns.index("PPID")
    except ValueError:
        raise ParseError(
            "header is missing a PID or PPID column; parse_ps_forest needs "
            "output from `ps -ef` or `ps -eo ...` with those columns",
            lineno,
            1,
            raw,
        ) from None

    if "CMD" in columns:
        cmd_col = columns.index("CMD")
    elif "COMMAND" in columns:
        cmd_col = columns.index("COMMAND")
    else:
        raise ParseError(
            "header must include a CMD or COMMAND column", lineno, 1, raw
        )

    if cmd_col != len(columns) - 1:
        raise ParseError(
            "CMD/COMMAND must be the last header column, since only the "
            "last column is allowed to contain spaces",
            lineno,
            1,
            raw,
        )

    return pid_col, ppid_col, cmd_col


def _parse_int_field(match: re.Match, field_name: str, lineno: int, raw: str) -> int:
    value = match.group()
    if not value.isdigit():
        raise ParseError(
            f"expected an integer {field_name}, found {value!r}",
            lineno,
            match.start() + 1,
            raw,
        )
    return int(value)


def _strip_forest_decoration(cmd: str) -> str:
    stripped = cmd.lstrip(" ")
    if stripped.startswith(_FOREST_MARKER):
        stripped = stripped[len(_FOREST_MARKER):].lstrip(" ")
    return stripped


def parse_ps_forest(text: str) -> list[Process]:
    """Parse `ps -ef` (with or without --forest) output into a forest of
    Process nodes, reconstructing parentage from the PID/PPID columns.

    Column positions come from the header line, so any `ps -eo ...`
    invocation that includes PID, PPID, and a trailing CMD/COMMAND column
    works too, not just the exact layout `ps -ef` prints.
    """
    numbered = list(enumerate(text.splitlines(), start=1))
    nonblank = [(lineno, raw) for lineno, raw in numbered if raw.strip()]
    if not nonblank:
        return []

    header_lineno, header_raw = nonblank[0]
    pid_col, ppid_col, cmd_col = _find_header_columns(header_raw, header_lineno)

    nodes: dict[int, Process] = {}
    ppid_of: dict[int, int] = {}
    order: list[int] = []

    for lineno, raw in nonblank[1:]:
        tokens = _tokens(raw)
        if len(tokens) <= cmd_col:
            raise ParseError(
                f"expected at least {cmd_col + 1} columns, found {len(tokens)}",
                lineno,
                1,
                raw,
            )

        pid = _parse_int_field(tokens[pid_col], "pid", lineno, raw)
        ppid = _parse_int_field(tokens[ppid_col], "ppid", lineno, raw)
        name = _strip_forest_decoration(raw[tokens[cmd_col].start():].rstrip())

        if not name:
            raise ParseError(
                "expected a command after the ps columns",
                lineno,
                tokens[cmd_col].start() + 1,
                raw,
            )

        if pid in nodes:
            raise ParseError(
                f"pid {pid} was already used on line {nodes[pid].line}",
                lineno,
                tokens[pid_col].start() + 1,
                raw,
            )

        nodes[pid] = Process(pid=pid, name=name, line=lineno)
        ppid_of[pid] = ppid
        order.append(pid)

    roots: list[Process] = []
    for pid in order:
        node = nodes[pid]
        parent = nodes.get(ppid_of[pid])
        if parent is None or parent is node:
            roots.append(node)
        else:
            parent.children.append(node)
            node.parent = parent

    return roots


def parse_ps_forest_file(path) -> list[Process]:
    """Read a file and parse it as `ps -ef` / `ps -ef --forest` output."""
    with open(path, "r", encoding="utf-8") as handle:
        return parse_ps_forest(handle.read())
