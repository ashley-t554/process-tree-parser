import unittest

from proctree import parse, render


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


if __name__ == "__main__":
    unittest.main()
