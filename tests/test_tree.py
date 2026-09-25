import unittest

from proctree import parse, render, serialize


class ProcessWalkTests(unittest.TestCase):
    def setUp(self):
        text = "1 init\n  100 sshd\n    142 bash\n  120 cron\n"
        (self.init,) = parse(text)
        self.sshd, self.cron = self.init.children
        (self.bash,) = self.sshd.children

    def test_walk_is_depth_first_preorder(self):
        pids = [p.pid for p in self.init.walk()]
        self.assertEqual(pids, [1, 100, 142, 120])

    def test_find_locates_descendant_by_pid(self):
        self.assertIs(self.init.find(142), self.bash)
        self.assertIs(self.init.find(1), self.init)
        self.assertIsNone(self.init.find(9999))

    def test_ancestors_go_from_immediate_parent_to_root(self):
        self.assertEqual(list(self.bash.ancestors()), [self.sshd, self.init])
        self.assertEqual(list(self.init.ancestors()), [])

    def test_depth_counts_ancestors(self):
        self.assertEqual(self.init.depth(), 0)
        self.assertEqual(self.sshd.depth(), 1)
        self.assertEqual(self.bash.depth(), 2)

    def test_siblings_excludes_self_and_preserves_order(self):
        self.assertEqual(list(self.sshd.siblings()), [self.cron])
        self.assertEqual(list(self.cron.siblings()), [self.sshd])
        self.assertEqual(list(self.bash.siblings()), [])

    def test_siblings_of_a_root_is_empty(self):
        self.assertEqual(list(self.init.siblings()), [])

    def test_subtree_size_includes_self_and_all_descendants(self):
        self.assertEqual(self.init.subtree_size(), 4)
        self.assertEqual(self.sshd.subtree_size(), 2)
        self.assertEqual(self.bash.subtree_size(), 1)


class RenderTests(unittest.TestCase):
    def test_render_matches_readme_example(self):
        text = "1 init\n  100 sshd\n    142 bash\n  120 cron\n"
        roots = parse(text)
        self.assertEqual(
            render(roots),
            "1 init\n"
            "├─ 100 sshd\n"
            "│  └─ 142 bash\n"
            "└─ 120 cron",
        )

    def test_render_multiple_roots(self):
        roots = parse("1 init\n2 kthreadd\n")
        self.assertEqual(render(roots), "1 init\n2 kthreadd")

    def test_render_single_node(self):
        roots = parse("1 init\n")
        self.assertEqual(render(roots), "1 init")


class SerializeTests(unittest.TestCase):
    def test_serialize_matches_default_two_space_indent(self):
        text = "1 init\n  100 sshd\n    142 bash\n  120 cron\n"
        roots = parse(text)
        self.assertEqual(
            serialize(roots),
            "1 init\n  100 sshd\n    142 bash\n  120 cron",
        )

    def test_serialize_respects_indent_argument(self):
        roots = parse("1 init\n  100 sshd\n")
        self.assertEqual(serialize(roots, indent=4), "1 init\n    100 sshd")

    def test_serialize_multiple_roots(self):
        roots = parse("1 init\n2 kthreadd\n")
        self.assertEqual(serialize(roots), "1 init\n2 kthreadd")

    def test_round_trip_preserves_tree_shape(self):
        text = (
            "1 init\n"
            "  100 sshd\n"
            "    142 sshd: alice [priv]\n"
            "      143 bash\n"
            "  120 cron\n"
            "    121 sh -c backup.sh\n"
        )
        original = parse(text)
        round_tripped = parse(serialize(original))

        original_shape = [(p.pid, p.name, p.line) for p in original[0].walk()]
        round_tripped_shape = [(p.pid, p.name) for p in round_tripped[0].walk()]

        self.assertEqual(
            [(pid, name) for pid, name, _ in original_shape], round_tripped_shape
        )
        # re-parsing renumbers `line` to match the serialized text, not the
        # original source
        self.assertEqual([p.line for p in round_tripped[0].walk()], [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
