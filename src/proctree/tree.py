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
