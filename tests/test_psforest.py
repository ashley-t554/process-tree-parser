import os
import tempfile
import unittest

from proctree import ParseError, parse_ps_forest, parse_ps_forest_file

PLAIN_PS_EF = (
    "UID        PID  PPID  C STIME TTY          TIME CMD\n"
    "root         1     0  0 Sep16 ?        00:00:01 init\n"
    "root       100     1  0 Sep16 ?        00:00:00 sshd\n"
    "root       142   100  0 Sep16 ?        00:00:00 sshd: alice [priv]\n"
    "alice      143   142  0 Sep16 ?        00:00:00 bash\n"
    "alice      200   143  0 Sep16 pts/0    00:00:00 python worker.py\n"
    "root       120     1  0 Sep16 ?        00:00:00 cron\n"
    "root       121   120  0 Sep16 ?        00:00:00 sh -c backup.sh\n"
)

FOREST_PS_EF = (
    "UID        PID  PPID  C STIME TTY          TIME CMD\n"
    "root         1     0  0 Sep16 ?        00:00:01 init\n"
    "root       100     1  0 Sep16 ?        00:00:00 sshd\n"
    "root       142   100  0 Sep16 ?        00:00:00  \\_ sshd: alice [priv]\n"
    "alice      143   142  0 Sep16 ?        00:00:00      \\_ bash\n"
    "alice      200   143  0 Sep16 pts/0    00:00:00          \\_ python worker.py\n"
    "root       120     1  0 Sep16 ?        00:00:00  \\_ cron\n"
    "root       121   120  0 Sep16 ?        00:00:00      \\_ sh -c backup.sh\n"
)


def _shape(roots):
    return [(p.pid, p.name, p.parent.pid if p.parent else None) for r in roots for p in r.walk()]


class ParsePlainTests(unittest.TestCase):
    def test_tree_shape_matches_ppid_columns(self):
        roots = parse_ps_forest(PLAIN_PS_EF)
        self.assertEqual([r.pid for r in roots], [1])
        (init,) = roots
        sshd, cron = init.children
        self.assertEqual(sshd.pid, 100)
        self.assertEqual(cron.pid, 120)
        (priv,) = sshd.children
        self.assertEqual(priv.name, "sshd: alice [priv]")
        (bash,) = priv.children
        (worker,) = bash.children
        self.assertEqual(worker.name, "python worker.py")

    def test_line_numbers_are_recorded(self):
        (init,) = parse_ps_forest(PLAIN_PS_EF)
        self.assertEqual(init.line, 2)


class ParseForestDecorationTests(unittest.TestCase):
    def test_forest_markers_and_indentation_are_stripped(self):
        self.assertEqual(_shape(parse_ps_forest(FOREST_PS_EF)), _shape(parse_ps_forest(PLAIN_PS_EF)))

    def test_order_of_lines_does_not_matter(self):
        lines = PLAIN_PS_EF.splitlines()
        header, rows = lines[0], lines[1:]
        reordered = "\n".join([header] + list(reversed(rows))) + "\n"
        self.assertEqual(_shape(parse_ps_forest(reordered)), _shape(parse_ps_forest(PLAIN_PS_EF)))


class CustomColumnsTests(unittest.TestCase):
    def test_eo_style_header_with_only_needed_columns(self):
        text = (
            "PID  PPID CMD\n"
            "1    0    init\n"
            "100  1    sshd\n"
        )
        (init,) = parse_ps_forest(text)
        (sshd,) = init.children
        self.assertEqual(sshd.pid, 100)

    def test_command_header_is_accepted(self):
        text = "PID PPID COMMAND\n1 0 init\n"
        (init,) = parse_ps_forest(text)
        self.assertEqual(init.name, "init")


class RootDetectionTests(unittest.TestCase):
    def test_process_whose_ppid_is_absent_becomes_a_root(self):
        text = "PID PPID CMD\n142 100 sshd: alice [priv]\n"
        (node,) = parse_ps_forest(text)
        self.assertEqual(node.pid, 142)
        self.assertIsNone(node.parent)

    def test_self_ppid_becomes_a_root_instead_of_its_own_parent(self):
        text = "PID PPID CMD\n1 1 init\n"
        (node,) = parse_ps_forest(text)
        self.assertIsNone(node.parent)
        self.assertEqual(node.children, [])


class EmptyInputTests(unittest.TestCase):
    def test_blank_text_returns_no_roots(self):
        self.assertEqual(parse_ps_forest(""), [])
        self.assertEqual(parse_ps_forest("\n\n"), [])


class ParseErrorTests(unittest.TestCase):
    def test_missing_pid_column_is_rejected(self):
        with self.assertRaises(ParseError) as ctx:
            parse_ps_forest("UID CMD\nroot init\n")
        self.assertIn("missing a PID or PPID column", ctx.exception.message)

    def test_missing_cmd_column_is_rejected(self):
        with self.assertRaises(ParseError) as ctx:
            parse_ps_forest("PID PPID\n1 0\n")
        self.assertIn("must include a CMD or COMMAND column", ctx.exception.message)

    def test_cmd_must_be_the_last_column(self):
        with self.assertRaises(ParseError) as ctx:
            parse_ps_forest("CMD PID PPID\ninit 1 0\n")
        self.assertIn("must be the last header column", ctx.exception.message)

    def test_non_integer_pid_reports_its_column(self):
        text = "PID PPID CMD\nabc 0 init\n"
        with self.assertRaises(ParseError) as ctx:
            parse_ps_forest(text)
        err = ctx.exception
        self.assertIn("found 'abc'", err.message)
        self.assertEqual((err.line, err.column), (2, 1))

    def test_duplicate_pid_reports_the_earlier_line(self):
        text = "PID PPID CMD\n1 0 init\n1 0 also-init\n"
        with self.assertRaises(ParseError) as ctx:
            parse_ps_forest(text)
        self.assertIn("pid 1 was already used on line 2", ctx.exception.message)

    def test_missing_command_is_rejected(self):
        with self.assertRaises(ParseError) as ctx:
            parse_ps_forest("PID PPID CMD\n1 0 \\_\n")
        self.assertIn("expected a command", ctx.exception.message)

    def test_too_few_columns_is_rejected(self):
        with self.assertRaises(ParseError) as ctx:
            parse_ps_forest("PID PPID CMD\n1 0\n")
        self.assertIn("expected at least 3 columns", ctx.exception.message)


class ParsePsForestFileTests(unittest.TestCase):
    def test_reads_and_parses_from_disk(self):
        fd, path = tempfile.mkstemp(suffix=".ps")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(PLAIN_PS_EF)
            roots = parse_ps_forest_file(path)
            self.assertEqual(roots[0].pid, 1)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
