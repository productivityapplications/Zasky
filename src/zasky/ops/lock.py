"""Host-level single-writer lock.

A second Zasky process must not open a room-claiming Switch connection. The
database lease arrives in Phase 2; this file lock is the Phase 1 guard.
"""

from __future__ import annotations

import fcntl
import os
from pathlib import Path


class SingleWriterLock:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._fd: int | None = None

    @property
    def path(self) -> Path:
        return self._path

    def acquire(self) -> None:
        if self._fd is not None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self._path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise RuntimeError(
                "Another Zasky writer holds the single-writer lock"
            ) from None
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.fsync(fd)
        self._fd = fd

    def release(self) -> None:
        fd = self._fd
        if fd is None:
            return
        self._fd = None
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def __enter__(self) -> SingleWriterLock:
        self.acquire()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()
