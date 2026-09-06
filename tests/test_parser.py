import os
import tempfile
import unittest

from proctree import ParseError, parse, parse_file


class ParseBasicsTests(unittest.TestCase):
    def test_single_root(self):
        roots = parse("1 init")
        self.assertEqual(len(roots), 1)
        root = roots[0]
        self.assertEqual((root.pid, root.name, root.line), (1, "init", 1))
        self.assertEqual(root.children, [])
        self.assertIsNone(root.parent)

    def test_multiple_roots(self):
        roots = parse("1 init\n2 kthreadd\n")
        self.assertEqual([r.pid for r in roots], [1, 2])
        self.assertEqual([r.parent for r in roots], [None, None])

    def test_nested_tree_shape(self):
        text = (
            "1 init\n"
            "  100 sshd\n"
            "    142 sshd: alice [priv]\n"
            "      143 bash\n"
            "        200 python worker.py\n"
            "  120 cron\n"
            "    121 sh -c backup.sh\n"
        )
        (init,) = parse(text)
        sshd, cron = init.children
        self.assertEqual(sshd.pid, 100)
        self.assertEqual(cron.pid, 120)

        (priv,) = sshd.children
        self.assertEqual(priv.name, "sshd: alice [priv]")

        (bash,) = priv.children
        self.assertEqual(bash.pid, 143)

        (worker,) = bash.children
        self.assertEqual(worker.name, "python worker.py")

        (backup,) = cron.children
        self.assertEqual(backup.name, "sh -c backup.sh")

        self.assertIs(worker.parent, bash)
        self.assertIs(backup.parent, cron)

    def test_indentation_width_can_vary_between_files(self):
        two_space = parse("1 init\n  100 sshd\n")
        four_space = parse("1 init\n    100 sshd\n")
        self.assertEqual(two_space[0].children[0].pid, 100)
        self.assertEqual(four_space[0].children[0].pid, 100)

    def test_dedent_to_partial_depth_attaches_to_nearest_enclosing_ancestor(self):
        # "3 c" is indented less than "2 b" but more than "1 a"; it doesn't
        # re-enter any indent level already on the stack, so it becomes a
        # sibling of "b" under "a" rather than a child of "b".
        text = "1 a\n    2 b\n   3 c\n"
        (a,) = parse(text)
        self.assertEqual([c.pid for c in a.children], [2, 3])

    def test_blank_lines_and_comments_are_ignored(self):
        text = (
            "\n"
            "1 init\n"
            "\n"
            "  # a comment, indented deeper than anything nearby\n"
            "  100 sshd\n"
            "   # another comment\n"
            "\n"
        )
        (init,) = parse(text)
        self.assertEqual([c.pid for c in init.children], [100])

    def test_comment_only_text_has_no_roots(self):
        self.assertEqual(parse("# just a comment\n"), [])

    def test_name_with_internal_whitespace_and_trailing_spaces(self):
        (root,) = parse("1   sshd: alice [priv]   \n")
        self.assertEqual(root.name, "sshd: alice [priv]")

    def test_pids_must_be_unique_across_whole_tree_not_just_siblings(self):
        text = "1 init\n  100 sshd\n2 other\n  100 cron\n"
        with self.assertRaises(ParseError) as ctx:
            parse(text)
        self.assertIn("pid 100 was already used on line 2", ctx.exception.message)


class ParseErrorPositionTests(unittest.TestCase):
    def test_non_integer_pid(self):
        with self.assertRaises(ParseError) as ctx:
            parse("abc process\n")
        err = ctx.exception
        self.assertIn("found 'abc'", err.message)
        self.assertEqual((err.line, err.column), (1, 1))

    def test_missing_name_after_pid(self):
        with self.assertRaises(ParseError) as ctx:
            parse("42\n")
        err = ctx.exception
        self.assertEqual((err.line, err.column), (1, 3))

    def test_missing_name_after_pid_with_trailing_spaces(self):
        with self.assertRaises(ParseError) as ctx:
            parse("  42   \n")
        err = ctx.exception
        self.assertEqual((err.line, err.column), (1, 8))

    def test_tabs_in_indentation_are_rejected(self):
        with self.assertRaises(ParseError) as ctx:
            parse("1 init\n\t100 sshd\n")
        err = ctx.exception
        self.assertIn("tabs are not allowed", err.message)
        self.assertEqual((err.line, err.column), (2, 1))

    def test_unexpected_indentation_at_start_of_file(self):
        with self.assertRaises(ParseError) as ctx:
            parse("  1 init\n")
        err = ctx.exception
        self.assertIn("unexpected indentation", err.message)
        self.assertEqual((err.line, err.column), (1, 3))

    def test_duplicate_pid_error_matches_readme_example(self):
        text = "\n1 init\n  100 sshd\n  100 cron\n"
        with self.assertRaises(ParseError) as ctx:
            parse(text)
        err = ctx.exception
        self.assertEqual(err.message, "pid 100 was already used on line 3")
        self.assertEqual((err.line, err.column), (4, 3))
        self.assertEqual(
            str(err),
            "pid 100 was already used on line 3 (line 4, column 3)\n"
            "    4 |   100 cron\n"
            "      |   ^",
        )

    def test_error_carries_the_offending_source_line(self):
        with self.assertRaises(ParseError) as ctx:
            parse("1 init\n  nope\n")
        self.assertEqual(ctx.exception.source_line, "  nope")


class ParseFileTests(unittest.TestCase):
    def test_parse_file_reads_and_parses(self):
        fd, path = tempfile.mkstemp(suffix=".tree")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("1 init\n  100 sshd\n")
            roots = parse_file(path)
            self.assertEqual(roots[0].children[0].pid, 100)
        finally:
            os.remove(path)

    def test_parse_file_error_reports_position(self):
        fd, path = tempfile.mkstemp(suffix=".tree")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("1 init\n  100\n")
            with self.assertRaises(ParseError) as ctx:
                parse_file(path)
            self.assertEqual((ctx.exception.line, ctx.exception.column), (2, 6))
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
