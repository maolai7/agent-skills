"""Basic checks for platform entrypoints."""

from __future__ import annotations

import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


class EntrypointTests(unittest.TestCase):
    def test_python_env_wrapper_exists(self) -> None:
        self.assertTrue((SCRIPT_DIR / "check_env.py").exists())

    def test_python_fetch_wrapper_exists(self) -> None:
        self.assertTrue((SCRIPT_DIR / "fetch_article.py").exists())


if __name__ == "__main__":
    unittest.main()
