from dataclasses import dataclass, field


@dataclass
class Process:
    """A single node in a parsed process tree.

    `line` is the 1-based source line the process was declared on, kept
    around so downstream tools can report their own errors ("pid 4021 has
    no listening socket, see fixture.tree:7") without re-parsing.
    """

    pid: int
    name: str
    line: int
    children: list["Process"] = field(default_factory=list)
    parent: "Process | None" = None

    def walk(self):
        """Yield this process and all descendants, depth first."""
        yield self
        for child in self.children:
            yield from child.walk()

    def find(self, pid: int) -> "Process | None":
        """Return the descendant (or self) with the given pid, if any."""
        for process in self.walk():
            if process.pid == pid:
                return process
        return None

    def ancestors(self):
        """Yield parents from immediate parent up to the root."""
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    def depth(self) -> int:
        """Return how many ancestors this process has; a root is 0."""
        return sum(1 for _ in self.ancestors())

    def siblings(self):
        """Yield the other children of this process's parent, in order.

        A root has no `parent` to derive siblings from, even if it was
        parsed alongside other roots in the same forest, so this yields
        nothing for a root.
        """
        if self.parent is None:
            return
        for sibling in self.parent.children:
            if sibling is not self:
                yield sibling

    def subtree_size(self) -> int:
        """Return the number of processes in this subtree, including self."""
        return sum(1 for _ in self.walk())


def render(roots: list[Process]) -> str:
    """Render a forest of processes as an ASCII tree, e.g.:

        1 init
        ├─ 100 sshd
        │  └─ 200 bash
        └─ 150 cron
    """
    lines: list[str] = []

    def walk(node: Process, prefix: str, is_last: bool, is_root: bool) -> None:
        if is_root:
            lines.append(f"{node.pid} {node.name}")
            child_prefix = prefix
        else:
            connector = "└─ " if is_last else "├─ "
            lines.append(f"{prefix}{connector}{node.pid} {node.name}")
            child_prefix = prefix + ("   " if is_last else "│  ")
        for index, child in enumerate(node.children):
            walk(child, child_prefix, index == len(node.children) - 1, False)

    for index, root in enumerate(roots):
        walk(root, "", index == len(roots) - 1, True)

    return "\n".join(lines)


def serialize(roots: list[Process], indent: int = 2) -> str:
    """Render a forest of processes back into the indented text format
    accepted by `parse`, so `parse(serialize(parse(text)))` reproduces the
    same tree (though not necessarily the original whitespace or comments).

    `indent` is the number of spaces added per nesting level.
    """
    lines: list[str] = []

    def walk(node: Process, depth: int) -> None:
        lines.append(f"{' ' * (depth * indent)}{node.pid} {node.name}")
        for child in node.children:
            walk(child, depth + 1)

    for root in roots:
        walk(root, 0)

    return "\n".join(lines)
