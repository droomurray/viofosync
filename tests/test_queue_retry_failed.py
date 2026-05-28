"""Tests for queue.retry_failed."""
from __future__ import annotations

import time


def test_retry_failed_resets_state_and_attempts(tmp_path):
    from web.db import Database
    from web.services.queue import retry_failed
    db = Database(str(tmp_path / "v.db"))
    now = int(time.time())
    with db.write() as c:
        c.execute(
            "INSERT INTO download_queue "
            "(filename, source_dir, state, enqueued_at, attempts, last_error) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("a.MP4", "/DCIM", "failed", now, 3, "boom"),
        )
        c.execute(
            "INSERT INTO download_queue "
            "(filename, source_dir, state, enqueued_at, attempts) "
            "VALUES (?, ?, ?, ?, ?)",
            ("b.MP4", "/DCIM", "pending", now, 0),
        )
    n = retry_failed(db)
    assert n == 1
    with db.conn() as c:
        rows = {r["filename"]: dict(r) for r in c.execute(
            "SELECT * FROM download_queue"
        ).fetchall()}
    assert rows["a.MP4"]["state"] == "pending"
    assert rows["a.MP4"]["attempts"] == 0
    assert rows["a.MP4"]["last_error"] is None
    assert rows["b.MP4"]["state"] == "pending"  # untouched


def test_retry_failed_noop_when_no_failed_rows(tmp_path):
    from web.db import Database
    from web.services.queue import retry_failed
    db = Database(str(tmp_path / "v.db"))
    assert retry_failed(db) == 0
