from __future__ import annotations

import pytest

from zasky.ops.lock import SingleWriterLock


def test_second_writer_is_refused(tmp_path) -> None:
    first = SingleWriterLock(tmp_path / "zasky.lock")
    second = SingleWriterLock(tmp_path / "zasky.lock")
    first.acquire()
    try:
        with pytest.raises(RuntimeError, match="Another Zasky writer"):
            second.acquire()
    finally:
        first.release()

    # The lock is reusable after release.
    second.acquire()
    second.release()
