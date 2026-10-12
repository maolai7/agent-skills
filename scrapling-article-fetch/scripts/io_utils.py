"""Shared stdio helpers for cross-platform CLI output."""

from __future__ import annotations

import os
import sys
from typing import TextIO


def _force_utf8_env() -> None:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def _reconfigure_stream(stream: TextIO) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")


def configure_utf8_stdio(
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> None:
    """Ensure CLI output uses UTF-8 so article content prints on Windows."""

    _force_utf8_env()
    _reconfigure_stream(stdout or sys.stdout)
    _reconfigure_stream(stderr or sys.stderr)
