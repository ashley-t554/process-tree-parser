# proctree

A small library for reading process trees written as plain indented text,
and for building them from Python.

## Why

If you write tools that walk a process tree — an orphan reaper, a cgroup
auditor, a "find every descendant of this shell" script — you eventually
need test fixtures that describe process trees. Capturing real `ps -ef
--forest` output works until the test runs on a different machine and the
pids or process names shift, and hand-building `Process` objects in a test
file makes the shape of the tree hard to see at a glance.

This library parses a plain text notation instead:

```
1 init
  100 sshd
    142 sshd: alice [priv]
      143 bash
        200 python worker.py
  120 cron
    121 sh -c backup.sh
```

into a tree of `Process` objects, or back out again as the same kind of
text. The format is deliberately close to `pstree -p` output, so real
process dumps are easy to reshape into fixtures by hand.

## Usage

```python
from proctree import parse, render

text = """
1 init
  100 sshd
    142 bash
  120 cron
"""

roots = parse(text)
init = roots[0]

print(init.name)               # "init"
print([c.pid for c in init.children])   # [100, 120]

bash = init.find(142)
print([p.pid for p in bash.ancestors()])  # [100, 1]

print(render(roots))
```

```
1 init
├─ 100 sshd
│  └─ 142 bash
└─ 120 cron
```

## Error messages

The point of this library is that a malformed fixture should tell you
exactly where it's broken, not just that parsing failed somewhere:

```python
from proctree import parse, ParseError

text = """
1 init
  100 sshd
  100 cron
"""

try:
    parse(text)
except ParseError as err:
    print(err)
```

```
pid 100 was already used on line 3 (line 4, column 3)
    4 |   100 cron
      |   ^
```

Every `ParseError` carries `.message`, `.line`, `.column`, and
`.source_line` individually too, in case a caller wants to fold the
position into its own error format rather than print proctree's.

## Format

- Each non-blank, non-comment line is `<pid> <name>`.
- A line's depth is however many spaces it's indented past the line
  above it; indentation width does not need to be uniform across the
  file, only consistent within one nesting step.
- Tabs in indentation are rejected rather than silently expanded.
- Lines starting with `#` (after indentation) are comments.
- pids must be unique across the whole tree.

## Testing

The test suite uses only the standard library `unittest` module and runs
straight from a checkout, no install required:

```
python -m unittest discover -s tests
```

## Status

Early skeleton. The parser, `Process`/`render`, and error formatting work
and are covered by a test suite; no serializer or CLI yet.

## License

MIT, see LICENSE.
