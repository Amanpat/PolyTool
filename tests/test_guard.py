import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "guard"))

from guardlib import collect_forbidden, find_tracked_private, is_forbidden, normalize_path


class GuardLibTests(unittest.TestCase):
    def test_normalize_path(self) -> None:
        self.assertEqual(normalize_path("kb\\README.md"), "kb/README.md")
        self.assertEqual(normalize_path("./artifacts/report.txt"), "artifacts/report.txt")

    def test_allowlist_paths(self) -> None:
        blocked, reason = is_forbidden("kb/README.md")
        self.assertFalse(blocked)
        self.assertEqual(reason, "")
        blocked, reason = is_forbidden("kb/.gitkeep")
        self.assertFalse(blocked)
        self.assertEqual(reason, "")

    def test_blocks_kb_and_artifacts(self) -> None:
        blocked, reason = is_forbidden("kb/notes/private.txt")
        self.assertTrue(blocked)
        self.assertEqual(reason, "private kb path")
        blocked, reason = is_forbidden("artifacts/report.txt")
        self.assertTrue(blocked)
        self.assertEqual(reason, "artifacts path")

    def test_blocks_env_and_secrets_like(self) -> None:
        blocked, reason = is_forbidden(".env")
        self.assertTrue(blocked)
        self.assertEqual(reason, "env file")
        blocked, reason = is_forbidden("configs/secret_keys.json")
        self.assertTrue(blocked)
        self.assertEqual(reason, "secrets-like filename")

    def test_collect_forbidden(self) -> None:
        paths = [
            "kb/README.md",
            "docs/secret_notes.txt",
            "artifacts/export.csv",
            "exports/response_123.json",
        ]
        forbidden = collect_forbidden(paths)
        self.assertEqual(
            forbidden,
            [
                ("docs/secret_notes.txt", "secrets-like filename"),
                ("artifacts/export.csv", "artifacts path"),
                ("exports/response_123.json", "response json export"),
            ],
        )

    def test_find_tracked_private(self) -> None:
        tracked = [
            "kb/README.md",
            "kb/.gitkeep",
            "kb/Notes.txt",
            "artifacts/report.txt",
            "docs/README.md",
        ]
        self.assertEqual(
            find_tracked_private(tracked),
            ["kb/Notes.txt", "artifacts/report.txt"],
        )


if __name__ == "__main__":
    unittest.main()
