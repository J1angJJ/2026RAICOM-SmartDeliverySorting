from __future__ import annotations

import os
import select
import sys
import termios
import tty
from types import TracebackType
from typing import TextIO


class TerminalKeys:
    """Read single keys over a local or SSH terminal and restore it on exit."""

    def __init__(self, stream: TextIO = sys.stdin):
        self.stream = stream
        self.fd = stream.fileno()
        self._saved: list | None = None

    def __enter__(self) -> "TerminalKeys":
        if not self.stream.isatty():
            raise RuntimeError("当前标准输入不是交互终端")
        self._saved = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._saved is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self._saved)
            self._saved = None

    def read(self, timeout: float = 0.0) -> str | None:
        readable, _, _ = select.select([self.fd], [], [], max(0.0, timeout))
        if not readable:
            return None
        raw = os.read(self.fd, 1)
        return raw.decode("utf-8", errors="ignore") or None
