"""Tests for stdio helpers used by the scrapling article fetch skill."""

from __future__ import annotations

import io
import unittest

from io_utils import configure_utf8_stdio


class ConfigureUtf8StdioTests(unittest.TestCase):
    def test_reconfigures_text_streams_to_utf8(self) -> None:
        stream = io.TextIOWrapper(io.BytesIO(), encoding="gbk")

        configure_utf8_stdio(stdout=stream, stderr=stream)

        self.assertEqual(stream.encoding.lower(), "utf-8")


if __name__ == "__main__":
    unittest.main()
